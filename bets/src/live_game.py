from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

MLB_API_V11 = "https://statsapi.mlb.com/api/v1.1"


class LiveGameError(RuntimeError):
    pass


def _get_json(url: str, *, timeout: int = 20) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise LiveGameError(f"MLB live-feed request failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise LiveGameError("MLB returned an unexpected live-feed response.")
    return payload


def fetch_live_game_state(game_pk: int) -> dict[str, Any]:
    payload = _get_json(f"{MLB_API_V11}/game/{game_pk}/feed/live")

    game_data = payload.get("gameData", {})
    live_data = payload.get("liveData", {})
    linescore = live_data.get("linescore", {})
    plays = live_data.get("plays", {})
    current_play = plays.get("currentPlay") or {}
    matchup = current_play.get("matchup", {})
    count = current_play.get("count", {})
    result = current_play.get("result", {})
    about = current_play.get("about", {})
    offense = linescore.get("offense", {})
    teams = linescore.get("teams", {})
    box_teams = live_data.get("boxscore", {}).get("teams", {})

    status = game_data.get("status", {})
    abstract_state = status.get("abstractGameState")
    detailed_state = status.get("detailedState")

    away_team = game_data.get("teams", {}).get("away", {}).get("name")
    home_team = game_data.get("teams", {}).get("home", {}).get("name")
    away_score = teams.get("away", {}).get("runs", 0) or 0
    home_score = teams.get("home", {}).get("runs", 0) or 0

    batter = matchup.get("batter", {})
    pitcher = matchup.get("pitcher", {})

    return {
        "game_pk": game_pk,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "abstract_state": abstract_state,
        "detailed_state": detailed_state,
        "is_live": abstract_state == "Live",
        "is_final": abstract_state == "Final",
        "away_team": away_team,
        "home_team": home_team,
        "away_score": int(away_score),
        "home_score": int(home_score),
        "current_inning": linescore.get("currentInning"),
        "inning_ordinal": linescore.get("currentInningOrdinal"),
        "inning_state": linescore.get("inningState"),
        "inning_half": linescore.get("inningHalf"),
        "outs": int(linescore.get("outs") or count.get("outs") or 0),
        "balls": int(count.get("balls") or 0),
        "strikes": int(count.get("strikes") or 0),
        "runner_on_first": bool(offense.get("first")),
        "runner_on_second": bool(offense.get("second")),
        "runner_on_third": bool(offense.get("third")),
        "batter": batter.get("fullName"),
        "batter_id": batter.get("id"),
        "pitcher": pitcher.get("fullName"),
        "pitcher_id": pitcher.get("id"),
        "at_bat_description": result.get("description"),
        "event": result.get("event"),
        "is_complete_at_bat": about.get("isComplete"),
        "away_lineup_count": len(box_teams.get("away", {}).get("battingOrder", []) or []),
        "home_lineup_count": len(box_teams.get("home", {}).get("battingOrder", []) or []),
        "raw_status": status,
    }


def base_state_text(state: dict[str, Any]) -> str:
    occupied = []
    if state.get("runner_on_first"):
        occupied.append("1st")
    if state.get("runner_on_second"):
        occupied.append("2nd")
    if state.get("runner_on_third"):
        occupied.append("3rd")
    return ", ".join(occupied) if occupied else "Bases empty"


def inning_text(state: dict[str, Any]) -> str:
    if state.get("is_final"):
        return state.get("detailed_state") or "Final"
    ordinal = state.get("inning_ordinal") or ""
    inning_state = state.get("inning_state") or state.get("inning_half") or ""
    text = f"{inning_state} {ordinal}".strip()
    return text or (state.get("detailed_state") or "Pregame")


def live_watch_label(
    *,
    state: dict[str, Any],
    pregame_leader: str | None,
    adjusted_leader_score: float | None,
    coverage: float | None,
) -> dict[str, str]:
    """
    A transparent watch rule for the interface. This is intentionally not
    presented as a validated betting model.
    """
    if state.get("is_final"):
        return {
            "label": "GAME FINAL",
            "tone": "gray",
            "reason": "The game has ended.",
        }

    if not state.get("is_live"):
        return {
            "label": "PREGAME",
            "tone": "gray",
            "reason": "Live-entry rules activate when MLB marks the game in progress.",
        }

    if not pregame_leader:
        return {
            "label": "NO PREGAME LEAN",
            "tone": "gray",
            "reason": "The pregame matchup score was tied or unavailable.",
        }

    away = state.get("away_team")
    home = state.get("home_team")
    away_score = int(state.get("away_score") or 0)
    home_score = int(state.get("home_score") or 0)
    inning = int(state.get("current_inning") or 1)

    leader_score = away_score if pregame_leader == away else home_score
    opponent_score = home_score if pregame_leader == away else away_score
    margin = leader_score - opponent_score

    adjusted = adjusted_leader_score or 50.0
    data_coverage = coverage or 0.0

    if inning <= 5 and margin in (-2, -1) and adjusted >= 56 and data_coverage >= 25:
        return {
            "label": "BETTER-PRICE WATCH",
            "tone": "yellow",
            "reason": (
                f"The pregame lean ({pregame_leader}) trails by {abs(margin)} early. "
                "That can create a better live moneyline, but wait for the current at-bat "
                "or half-inning to finish before comparing the price."
            ),
        }

    if inning <= 4 and margin == 0 and adjusted >= 58 and data_coverage >= 30:
        return {
            "label": "LIVE ENTRY WATCH",
            "tone": "green",
            "reason": (
                f"The game remains tied early and {pregame_leader} carried the stronger "
                "coverage-adjusted pregame profile. Compare the live price with the pregame price."
            ),
        }

    if margin >= 3:
        return {
            "label": "DO NOT CHASE",
            "tone": "red",
            "reason": (
                f"{pregame_leader} already leads by {margin}. The live moneyline may be too expensive."
            ),
        }

    if inning >= 7 and margin < 0:
        return {
            "label": "LATE COMEBACK RISK",
            "tone": "red",
            "reason": (
                f"The pregame lean trails in the {inning_text(state)}. "
                "Do not treat the original pregame score as a reason to force a late entry."
            ),
        }

    return {
        "label": "MONITOR",
        "tone": "gray",
        "reason": (
            "The current game state does not meet the provisional live-entry watch rules."
        ),
    }
