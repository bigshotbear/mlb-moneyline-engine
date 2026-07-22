from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import requests

MLB_API_V1 = "https://statsapi.mlb.com/api/v1"


class TeamRankingError(RuntimeError):
    pass


def _get_json(url: str, *, params: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise TeamRankingError(f"MLB ranking request failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise TeamRankingError("MLB returned an unexpected ranking response.")
    return payload


def _window_dates(as_of_date: date, window: str) -> tuple[date, date]:
    # Lock all trend inputs to the day before the scheduled game.
    end_date = as_of_date - timedelta(days=1)

    if window == "season":
        start_date = date(as_of_date.year, 3, 1)
    elif window == "month":
        start_date = end_date - timedelta(days=29)
    elif window == "week":
        start_date = end_date - timedelta(days=6)
    else:
        raise ValueError(f"Unknown window: {window}")

    return start_date, end_date


def _extract_team_splits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for block in payload.get("stats", []):
        splits = block.get("splits", [])
        if splits:
            return splits
    return []


def _fetch_category(
    *,
    season: int,
    start_date: date,
    end_date: date,
    group: str,
    sort_stat: str,
    order: str,
    sit_code: str | None = None,
) -> dict[int, dict[str, Any]]:
    params: dict[str, Any] = {
        "season": season,
        "sportIds": 1,
        "gameType": "R",
        "stats": "byDateRange",
        "group": group,
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "sortStat": sort_stat,
        "order": order,
        "limit": 40,
    }
    if sit_code:
        params["sitCodes"] = sit_code

    payload = _get_json(f"{MLB_API_V1}/teams/stats", params=params)
    result: dict[int, dict[str, Any]] = {}

    for split in _extract_team_splits(payload):
        team = split.get("team", {})
        team_id = team.get("id")
        if not team_id:
            continue

        rank_value = split.get("rank")
        try:
            rank = int(rank_value)
        except (TypeError, ValueError):
            rank = None

        result[int(team_id)] = {
            "rank": rank,
            "team": team.get("name"),
            "stat": split.get("stat", {}),
        }

    return result


def _metric_value(category: str, stat: dict[str, Any]) -> tuple[str, str]:
    if category == "batting":
        value = stat.get("ops") or stat.get("onBasePlusSlugging")
        return ("OPS", str(value) if value is not None else "N/A")

    value = stat.get("era")
    return ("ERA", str(value) if value is not None else "N/A")


def _entry(
    category: str,
    category_rows: dict[int, dict[str, Any]],
    team_id: int,
) -> dict[str, Any]:
    row = category_rows.get(team_id, {})
    metric_name, metric_value = _metric_value(category, row.get("stat", {}))
    return {
        "rank": row.get("rank"),
        "metric_name": metric_name,
        "metric_value": metric_value,
        "available": bool(row),
    }


def fetch_league_rankings(as_of_date: date) -> dict[str, Any]:
    """
    Fetch all 30 clubs in nine compact requests:
    3 windows x batting / starting pitching / relief pitching.

    `sp` and `rp` are MLB situation codes. If the endpoint does not return
    role-specific splits, the affected category remains unavailable rather than
    silently substituting total pitching.
    """
    response: dict[str, Any] = {
        "as_of_date": as_of_date.isoformat(),
        "windows": {},
        "warnings": [],
    }

    for window in ("season", "month", "week"):
        start_date, end_date = _window_dates(as_of_date, window)
        window_data: dict[str, Any] = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "batting": {},
            "starting_pitching": {},
            "bullpen": {},
        }

        requests_to_make = (
            ("batting", "hitting", "onBasePlusSlugging", "desc", None),
            ("starting_pitching", "pitching", "earnedRunAverage", "asc", "sp"),
            ("bullpen", "pitching", "earnedRunAverage", "asc", "rp"),
        )

        for category, group, sort_stat, order, sit_code in requests_to_make:
            try:
                window_data[category] = _fetch_category(
                    season=as_of_date.year,
                    start_date=start_date,
                    end_date=end_date,
                    group=group,
                    sort_stat=sort_stat,
                    order=order,
                    sit_code=sit_code,
                )
                if not window_data[category]:
                    response["warnings"].append(
                        f"No {category} rankings returned for {window}."
                    )
            except TeamRankingError as exc:
                response["warnings"].append(
                    f"{window} {category}: {exc}"
                )
                window_data[category] = {}

        response["windows"][window] = window_data

    return response


def team_profile(
    rankings: dict[str, Any],
    team_id: int | None,
) -> dict[str, Any]:
    if not team_id:
        return {
            "available": False,
            "batting": {},
            "starting_pitching": {},
            "bullpen": {},
        }

    profile: dict[str, Any] = {
        "available": True,
        "batting": {},
        "starting_pitching": {},
        "bullpen": {},
    }

    for category in ("batting", "starting_pitching", "bullpen"):
        for window in ("season", "month", "week"):
            rows = rankings.get("windows", {}).get(window, {}).get(category, {})
            profile[category][window] = _entry(category, rows, int(team_id))

    return profile


def average_rank(category_profile: dict[str, Any]) -> float | None:
    ranks = [
        value.get("rank")
        for value in category_profile.values()
        if value.get("rank") is not None
    ]
    if not ranks:
        return None
    return sum(ranks) / len(ranks)


def trend_label(category_profile: dict[str, Any]) -> str:
    season_rank = category_profile.get("season", {}).get("rank")
    week_rank = category_profile.get("week", {}).get("rank")

    if season_rank is None or week_rank is None:
        return "Data pending"

    change = season_rank - week_rank
    if change >= 5:
        return "🔥 Hot"
    if change <= -5:
        return "🧊 Cooling"
    return "➖ Steady"


def comparative_lean(
    away_category: dict[str, Any],
    home_category: dict[str, Any],
    away_name: str,
    home_name: str,
) -> dict[str, Any]:
    away_score = average_rank(away_category)
    home_score = average_rank(home_category)

    if away_score is None or home_score is None:
        return {
            "team": None,
            "label": "Data pending",
            "away_average_rank": away_score,
            "home_average_rank": home_score,
        }

    if abs(away_score - home_score) < 1.0:
        return {
            "team": None,
            "label": "Even",
            "away_average_rank": away_score,
            "home_average_rank": home_score,
        }

    team = away_name if away_score < home_score else home_name
    return {
        "team": team,
        "label": f"Supports {team}",
        "away_average_rank": away_score,
        "home_average_rank": home_score,
    }
