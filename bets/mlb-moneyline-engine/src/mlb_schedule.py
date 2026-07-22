from __future__ import annotations

from datetime import date
from typing import Any

import requests

SCHEDULE_ENDPOINT = "https://statsapi.mlb.com/api/v1/schedule"


class MLBScheduleError(RuntimeError):
    pass


def fetch_schedule(game_date: date, timeout: int = 20) -> list[dict[str, Any]]:
    params = {
        "sportId": 1,
        "date": game_date.isoformat(),
        "hydrate": "probablePitcher,team",
    }

    try:
        response = requests.get(SCHEDULE_ENDPOINT, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise MLBScheduleError(f"Could not load MLB schedule: {exc}") from exc

    games: list[dict[str, Any]] = []
    for date_block in payload.get("dates", []):
        for game in date_block.get("games", []):
            teams = game.get("teams", {})
            home = teams.get("home", {})
            away = teams.get("away", {})
            games.append(
                {
                    "game_pk": game.get("gamePk"),
                    "game_date": game.get("gameDate"),
                    "status": game.get("status", {}).get("detailedState"),
                    "home_team": home.get("team", {}).get("name"),
                    "away_team": away.get("team", {}).get("name"),
                    "home_probable_pitcher": home.get("probablePitcher", {}).get("fullName"),
                    "away_probable_pitcher": away.get("probablePitcher", {}).get("fullName"),
                }
            )
    return games


def _normalize_team_name(name: str | None) -> str:
    if not name:
        return ""
    normalized = " ".join(name.lower().replace(".", "").split())
    aliases = {"athletics": "oakland athletics"}
    return aliases.get(normalized, normalized)


def match_schedule_game(
    odds_game: dict[str, Any],
    schedule_games: list[dict[str, Any]],
) -> dict[str, Any] | None:
    odds_home = _normalize_team_name(odds_game.get("home_team"))
    odds_away = _normalize_team_name(odds_game.get("away_team"))

    for game in schedule_games:
        schedule_home = _normalize_team_name(game.get("home_team"))
        schedule_away = _normalize_team_name(game.get("away_team"))
        exact = odds_home == schedule_home and odds_away == schedule_away
        nickname_match = (
            odds_home.split()[-1:] == schedule_home.split()[-1:]
            and odds_away.split()[-1:] == schedule_away.split()[-1:]
        )
        if exact or nickname_match:
            return game
    return None
