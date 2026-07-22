from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Any

import requests

from .no_vig import remove_vig_two_way

ODDS_ENDPOINT = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"


class OddsAPIError(RuntimeError):
    pass


@dataclass
class OddsResponse:
    events: list[dict[str, Any]]
    remaining_requests: str | None
    used_requests: str | None
    fetched_at_utc: str


def fetch_mlb_moneylines(
    api_key: str,
    *,
    regions: str = "us",
    timeout: int = 20,
) -> OddsResponse:
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": "h2h",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }

    try:
        response = requests.get(ODDS_ENDPOINT, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise OddsAPIError(f"Could not reach The Odds API: {exc}") from exc

    if response.status_code != 200:
        raise OddsAPIError(
            f"The Odds API returned HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    try:
        events = response.json()
    except ValueError as exc:
        raise OddsAPIError("The Odds API returned invalid JSON.") from exc

    if not isinstance(events, list):
        raise OddsAPIError("Unexpected response format from The Odds API.")

    return OddsResponse(
        events=events,
        remaining_requests=response.headers.get("x-requests-remaining"),
        used_requests=response.headers.get("x-requests-used"),
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def _extract_h2h_outcomes(bookmaker: dict[str, Any]) -> dict[str, float]:
    for market in bookmaker.get("markets", []):
        if market.get("key") == "h2h":
            result: dict[str, float] = {}
            for outcome in market.get("outcomes", []):
                name = outcome.get("name")
                price = outcome.get("price")
                if name is not None and isinstance(price, (int, float)):
                    result[str(name)] = float(price)
            return result
    return {}


def parse_event(event: dict[str, Any]) -> dict[str, Any]:
    home = event.get("home_team", "Unknown home")
    away = event.get("away_team", "Unknown away")

    book_rows: list[dict[str, Any]] = []
    home_no_vig: list[float] = []
    away_no_vig: list[float] = []

    for bookmaker in event.get("bookmakers", []):
        outcomes = _extract_h2h_outcomes(bookmaker)
        if home not in outcomes or away not in outcomes:
            continue

        home_odds = outcomes[home]
        away_odds = outcomes[away]
        normalized = remove_vig_two_way(home_odds, away_odds)

        home_no_vig.append(normalized.side_a_probability)
        away_no_vig.append(normalized.side_b_probability)

        book_rows.append(
            {
                "bookmaker_key": bookmaker.get("key"),
                "bookmaker": bookmaker.get("title", bookmaker.get("key", "Unknown")),
                "last_update": bookmaker.get("last_update"),
                "home_team": home,
                "home_odds": int(home_odds),
                "home_no_vig": normalized.side_a_probability,
                "away_team": away,
                "away_odds": int(away_odds),
                "away_no_vig": normalized.side_b_probability,
                "hold": normalized.overround,
            }
        )

    return {
        "event_id": event.get("id"),
        "commence_time": event.get("commence_time"),
        "home_team": home,
        "away_team": away,
        "bookmakers": book_rows,
        "best_home_odds": max((r["home_odds"] for r in book_rows), default=None),
        "best_away_odds": max((r["away_odds"] for r in book_rows), default=None),
        "consensus_home_no_vig": median(home_no_vig) if home_no_vig else None,
        "consensus_away_no_vig": median(away_no_vig) if away_no_vig else None,
    }


def parse_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [parse_event(event) for event in events]
