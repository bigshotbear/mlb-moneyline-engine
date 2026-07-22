from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

MLB_API_V1 = "https://statsapi.mlb.com/api/v1"
MLB_API_V11 = "https://statsapi.mlb.com/api/v1.1"
EASTERN = ZoneInfo("America/New_York")


class MLBDataError(RuntimeError):
    pass


def _get_json(url: str, *, params: dict[str, Any] | None = None, timeout: int = 25) -> dict[str, Any]:
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise MLBDataError(f"MLB data request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise MLBDataError("MLB returned an unexpected response.")
    return payload


def event_date_eastern(commence_time: str | None) -> date:
    if not commence_time:
        return datetime.now(EASTERN).date()
    parsed = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(EASTERN).date()


def fetch_schedule(game_date: date) -> list[dict[str, Any]]:
    payload = _get_json(
        f"{MLB_API_V1}/schedule",
        params={"sportId": 1, "date": game_date.isoformat(), "hydrate": "probablePitcher,team"},
    )
    games: list[dict[str, Any]] = []
    for date_block in payload.get("dates", []):
        for game in date_block.get("games", []):
            teams = game.get("teams", {})
            home = teams.get("home", {})
            away = teams.get("away", {})
            games.append({
                "game_pk": game.get("gamePk"),
                "game_date": game.get("gameDate"),
                "status": game.get("status", {}).get("detailedState"),
                "home_team": home.get("team", {}).get("name"),
                "home_team_id": home.get("team", {}).get("id"),
                "away_team": away.get("team", {}).get("name"),
                "away_team_id": away.get("team", {}).get("id"),
                "home_probable_pitcher": home.get("probablePitcher", {}).get("fullName"),
                "home_probable_pitcher_id": home.get("probablePitcher", {}).get("id"),
                "away_probable_pitcher": away.get("probablePitcher", {}).get("fullName"),
                "away_probable_pitcher_id": away.get("probablePitcher", {}).get("id"),
            })
    return games


def _normalize_team_name(name: str | None) -> str:
    if not name:
        return ""
    normalized = " ".join(name.lower().replace(".", "").split())
    return {"athletics": "oakland athletics"}.get(normalized, normalized)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def match_schedule_game(odds_game: dict[str, Any], schedule_games: list[dict[str, Any]]) -> dict[str, Any] | None:
    odds_home = _normalize_team_name(odds_game.get("home_team"))
    odds_away = _normalize_team_name(odds_game.get("away_team"))
    candidates: list[dict[str, Any]] = []
    for game in schedule_games:
        schedule_home = _normalize_team_name(game.get("home_team"))
        schedule_away = _normalize_team_name(game.get("away_team"))
        exact = odds_home == schedule_home and odds_away == schedule_away
        nickname_match = (
            odds_home.split()[-1:] == schedule_home.split()[-1:]
            and odds_away.split()[-1:] == schedule_away.split()[-1:]
        )
        if exact or nickname_match:
            candidates.append(game)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    odds_time = _parse_time(odds_game.get("commence_time"))
    if odds_time is None:
        return candidates[0]
    def distance(game: dict[str, Any]) -> float:
        game_time = _parse_time(game.get("game_date"))
        return abs((game_time - odds_time).total_seconds()) if game_time else float("inf")
    return min(candidates, key=distance)


def fetch_game_lineups(game_pk: int) -> dict[str, Any]:
    payload = _get_json(f"{MLB_API_V11}/game/{game_pk}/feed/live")
    game_data = payload.get("gameData", {})
    teams = payload.get("liveData", {}).get("boxscore", {}).get("teams", {})
    return {
        "game_pk": game_pk,
        "status": game_data.get("status", {}).get("detailedState"),
        "away": _parse_lineup_side(teams.get("away", {})),
        "home": _parse_lineup_side(teams.get("home", {})),
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _parse_lineup_side(side_data: dict[str, Any]) -> dict[str, Any]:
    players = side_data.get("players", {})
    order = side_data.get("battingOrder", []) or []
    if not order:
        sortable: list[tuple[int, int]] = []
        for player in players.values():
            raw_order = player.get("battingOrder")
            person_id = player.get("person", {}).get("id")
            try:
                if raw_order and person_id:
                    sortable.append((int(raw_order), int(person_id)))
            except (TypeError, ValueError):
                continue
        order = [person_id for _, person_id in sorted(sortable)]
    lineup: list[dict[str, Any]] = []
    for batting_slot, person_id in enumerate(order, start=1):
        player = players.get(f"ID{person_id}", {})
        person = player.get("person", {})
        lineup.append({
            "order": batting_slot,
            "player_id": person.get("id", person_id),
            "player": person.get("fullName", f"Player {person_id}"),
            "position": player.get("position", {}).get("abbreviation"),
            "bats": person.get("batSide", {}).get("code"),
        })
    return {
        "team": side_data.get("team", {}).get("name"),
        "team_id": side_data.get("team", {}).get("id"),
        "lineup": lineup,
        "confirmed": len(lineup) >= 9,
    }


def fetch_pitcher_season_stats(person_id: int | None, season: int) -> dict[str, Any]:
    if not person_id:
        return {"available": False, "reason": "No probable-pitcher ID was available."}
    payload = _get_json(
        f"{MLB_API_V1}/people/{person_id}/stats",
        params={"stats": "season", "group": "pitching", "season": season, "gameType": "R"},
    )
    splits: list[dict[str, Any]] = []
    for block in payload.get("stats", []):
        splits.extend(block.get("splits", []))
    if not splits:
        return {"available": False, "person_id": person_id, "reason": "No current-season pitching line was returned."}
    split = splits[0]
    stat = split.get("stat", {})
    wins, losses = stat.get("wins"), stat.get("losses")
    return {
        "available": True,
        "person_id": person_id,
        "name": split.get("player", {}).get("fullName"),
        "season": season,
        "record": f"{wins}-{losses}" if wins is not None and losses is not None else None,
        "wins": wins,
        "losses": losses,
        "era": stat.get("era"),
        "whip": stat.get("whip"),
        "innings_pitched": stat.get("inningsPitched"),
        "games_started": stat.get("gamesStarted"),
        "strikeouts": stat.get("strikeOuts"),
        "walks": stat.get("baseOnBalls"),
        "strikeout_walk_ratio": stat.get("strikeoutWalkRatio"),
        "raw": stat,
    }


def _baseball_ip_to_outs(value: Any) -> int:
    if value in (None, ""):
        return 0
    text = str(value)
    if "." not in text:
        try:
            return int(text) * 3
        except ValueError:
            return 0
    whole, partial = text.split(".", 1)
    try:
        innings = int(whole)
        remainder = int(partial[:1] or "0")
    except ValueError:
        return 0
    return innings * 3 + (remainder if remainder in (0, 1, 2) else 0)


def _outs_to_baseball_ip(outs: int) -> str:
    return f"{outs // 3}.{outs % 3}"


def _recent_team_games(team_id: int, as_of_date: date, days: int = 3) -> list[dict[str, Any]]:
    payload = _get_json(
        f"{MLB_API_V1}/schedule",
        params={
            "sportId": 1,
            "teamId": team_id,
            "startDate": (as_of_date - timedelta(days=days)).isoformat(),
            "endDate": (as_of_date - timedelta(days=1)).isoformat(),
            "gameType": "R",
        },
    )
    games: list[dict[str, Any]] = []
    for date_block in payload.get("dates", []):
        block_date = date.fromisoformat(date_block.get("date"))
        for game in date_block.get("games", []):
            if game.get("status", {}).get("abstractGameState") == "Final":
                games.append({"game_pk": game.get("gamePk"), "date": block_date})
    return games


def _find_team_side(teams: dict[str, Any], team_id: int) -> dict[str, Any] | None:
    for side_name in ("home", "away"):
        side = teams.get(side_name, {})
        if side.get("team", {}).get("id") == team_id:
            return side
    return None


def fetch_bullpen_workload(team_id: int | None, as_of_date: date, days: int = 3) -> dict[str, Any]:
    if not team_id:
        return {"available": False, "reason": "No team ID was available."}
    recent_games = _recent_team_games(team_id, as_of_date, days)
    aggregate: dict[int, dict[str, Any]] = {}
    totals = defaultdict(int)
    for game in recent_games:
        boxscore = _get_json(f"{MLB_API_V1}/game/{game['game_pk']}/boxscore")
        side = _find_team_side(boxscore.get("teams", {}), team_id)
        if not side:
            continue
        pitchers = side.get("pitchers", []) or []
        starter_id = pitchers[0] if pitchers else None
        players = side.get("players", {})
        for pitcher_id in pitchers:
            player = players.get(f"ID{pitcher_id}", {})
            pitching = player.get("stats", {}).get("pitching", {})
            if pitching.get("gamesStarted") == 1 or pitcher_id == starter_id:
                continue
            days_ago = (as_of_date - game["date"]).days
            if not 1 <= days_ago <= days:
                continue
            pitches = int(pitching.get("numberOfPitches") or 0)
            outs = _baseball_ip_to_outs(pitching.get("inningsPitched"))
            entry = aggregate.setdefault(int(pitcher_id), {
                "player_id": int(pitcher_id),
                "player": player.get("person", {}).get("fullName", f"Pitcher {pitcher_id}"),
                "pitches_1d": 0, "pitches_2d": 0, "pitches_3d": 0,
                "outs_1d": 0, "outs_2d": 0, "outs_3d": 0,
                "appearances_3d": 0, "used_dates": set(),
            })
            entry["pitches_3d"] += pitches
            entry["outs_3d"] += outs
            entry["appearances_3d"] += 1
            entry["used_dates"].add(game["date"])
            totals["pitches_3d"] += pitches
            totals["outs_3d"] += outs
            if days_ago <= 2:
                entry["pitches_2d"] += pitches
                entry["outs_2d"] += outs
                totals["pitches_2d"] += pitches
                totals["outs_2d"] += outs
            if days_ago <= 1:
                entry["pitches_1d"] += pitches
                entry["outs_1d"] += outs
                totals["pitches_1d"] += pitches
                totals["outs_1d"] += outs
    relievers: list[dict[str, Any]] = []
    yesterday = as_of_date - timedelta(days=1)
    for entry in aggregate.values():
        dates = sorted(entry.pop("used_dates"), reverse=True)
        date_set = set(dates)
        consecutive = 0
        cursor = yesterday
        while cursor in date_set:
            consecutive += 1
            cursor -= timedelta(days=1)
        entry.update({
            "innings_1d": _outs_to_baseball_ip(entry.pop("outs_1d")),
            "innings_2d": _outs_to_baseball_ip(entry.pop("outs_2d")),
            "innings_3d": _outs_to_baseball_ip(entry.pop("outs_3d")),
            "consecutive_days": consecutive,
            "last_used": dates[0].isoformat() if dates else None,
        })
        relievers.append(entry)
    relievers.sort(key=lambda item: (item["pitches_3d"], item["appearances_3d"]), reverse=True)
    return {
        "available": True,
        "team_id": team_id,
        "as_of_date": as_of_date.isoformat(),
        "games_reviewed": len(recent_games),
        "summary": {
            "pitches_1d": totals["pitches_1d"],
            "pitches_2d": totals["pitches_2d"],
            "pitches_3d": totals["pitches_3d"],
            "innings_1d": _outs_to_baseball_ip(totals["outs_1d"]),
            "innings_2d": _outs_to_baseball_ip(totals["outs_2d"]),
            "innings_3d": _outs_to_baseball_ip(totals["outs_3d"]),
            "relievers_used_3d": len(relievers),
        },
        "relievers": relievers,
        "note": "Automated workload is not a definitive medical or manager-availability report.",
    }


def fetch_all_bullpen_workloads(
    as_of_date: date,
    days: int = 3,
    max_workers: int = 8,
) -> dict[int, dict[str, Any]]:
    """
    Build workload for all MLB teams from one league schedule and each completed
    boxscore. This is much faster than requesting a separate schedule per team.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    payload = _get_json(
        f"{MLB_API_V1}/schedule",
        params={
            "sportId": 1,
            "startDate": (as_of_date - timedelta(days=days)).isoformat(),
            "endDate": (as_of_date - timedelta(days=1)).isoformat(),
            "gameType": "R",
        },
    )

    games: list[dict[str, Any]] = []
    for date_block in payload.get("dates", []):
        try:
            block_date = date.fromisoformat(date_block.get("date"))
        except (TypeError, ValueError):
            continue
        for game in date_block.get("games", []):
            if game.get("status", {}).get("abstractGameState") == "Final":
                game_pk = game.get("gamePk")
                if game_pk:
                    games.append({"game_pk": int(game_pk), "date": block_date})

    def fetch_one(game: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        try:
            box = _get_json(f"{MLB_API_V1}/game/{game['game_pk']}/boxscore")
            return game, box
        except MLBDataError:
            return game, None

    aggregate: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
    totals: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    games_by_team: dict[int, set[int]] = defaultdict(set)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_one, game) for game in games]
        for future in as_completed(futures):
            game, boxscore = future.result()
            if not boxscore:
                continue

            for side_name in ("away", "home"):
                side = boxscore.get("teams", {}).get(side_name, {})
                team_id = side.get("team", {}).get("id")
                if not team_id:
                    continue
                team_id = int(team_id)
                games_by_team[team_id].add(game["game_pk"])

                pitchers = side.get("pitchers", []) or []
                starter_id = pitchers[0] if pitchers else None
                players = side.get("players", {})

                for pitcher_id in pitchers:
                    player = players.get(f"ID{pitcher_id}", {})
                    pitching = player.get("stats", {}).get("pitching", {})
                    if pitching.get("gamesStarted") == 1 or pitcher_id == starter_id:
                        continue

                    days_ago = (as_of_date - game["date"]).days
                    if not 1 <= days_ago <= days:
                        continue

                    pitches = int(pitching.get("numberOfPitches") or 0)
                    outs = _baseball_ip_to_outs(pitching.get("inningsPitched"))
                    pitcher_id = int(pitcher_id)

                    entry = aggregate[team_id].setdefault(
                        pitcher_id,
                        {
                            "player_id": pitcher_id,
                            "player": player.get("person", {}).get(
                                "fullName", f"Pitcher {pitcher_id}"
                            ),
                            "pitches_1d": 0,
                            "pitches_2d": 0,
                            "pitches_3d": 0,
                            "outs_1d": 0,
                            "outs_2d": 0,
                            "outs_3d": 0,
                            "appearances_3d": 0,
                            "used_dates": set(),
                        },
                    )

                    entry["pitches_3d"] += pitches
                    entry["outs_3d"] += outs
                    entry["appearances_3d"] += 1
                    entry["used_dates"].add(game["date"])
                    totals[team_id]["pitches_3d"] += pitches
                    totals[team_id]["outs_3d"] += outs

                    if days_ago <= 2:
                        entry["pitches_2d"] += pitches
                        entry["outs_2d"] += outs
                        totals[team_id]["pitches_2d"] += pitches
                        totals[team_id]["outs_2d"] += outs

                    if days_ago <= 1:
                        entry["pitches_1d"] += pitches
                        entry["outs_1d"] += outs
                        totals[team_id]["pitches_1d"] += pitches
                        totals[team_id]["outs_1d"] += outs

    output: dict[int, dict[str, Any]] = {}
    yesterday = as_of_date - timedelta(days=1)

    all_team_ids = set(aggregate) | set(games_by_team)
    for team_id in all_team_ids:
        relievers: list[dict[str, Any]] = []
        for entry in aggregate.get(team_id, {}).values():
            dates = sorted(entry.pop("used_dates"), reverse=True)
            date_set = set(dates)
            consecutive = 0
            cursor = yesterday
            while cursor in date_set:
                consecutive += 1
                cursor -= timedelta(days=1)

            entry.update(
                {
                    "innings_1d": _outs_to_baseball_ip(entry.pop("outs_1d")),
                    "innings_2d": _outs_to_baseball_ip(entry.pop("outs_2d")),
                    "innings_3d": _outs_to_baseball_ip(entry.pop("outs_3d")),
                    "consecutive_days": consecutive,
                    "last_used": dates[0].isoformat() if dates else None,
                }
            )
            relievers.append(entry)

        relievers.sort(
            key=lambda item: (item["pitches_3d"], item["appearances_3d"]),
            reverse=True,
        )
        team_totals = totals[team_id]
        output[team_id] = {
            "available": True,
            "team_id": team_id,
            "as_of_date": as_of_date.isoformat(),
            "games_reviewed": len(games_by_team.get(team_id, set())),
            "summary": {
                "pitches_1d": team_totals["pitches_1d"],
                "pitches_2d": team_totals["pitches_2d"],
                "pitches_3d": team_totals["pitches_3d"],
                "innings_1d": _outs_to_baseball_ip(team_totals["outs_1d"]),
                "innings_2d": _outs_to_baseball_ip(team_totals["outs_2d"]),
                "innings_3d": _outs_to_baseball_ip(team_totals["outs_3d"]),
                "relievers_used_3d": len(relievers),
            },
            "relievers": relievers,
            "note": (
                "Automated workload is not a definitive medical or manager-availability report."
            ),
        }

    return output
