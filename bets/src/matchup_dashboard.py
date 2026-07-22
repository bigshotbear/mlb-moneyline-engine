from __future__ import annotations

from html import escape
from typing import Any

from .team_rankings import comparative_lean, team_profile, trend_label
from .ui_helpers import format_game_time_et, format_moneyline


INDICATOR_LABELS = [
    ("SP", "Starting Pitcher"),
    ("MATCH", "Starter vs Lineup"),
    ("LINEUP", "Lineup"),
    ("BP", "Bullpen"),
    ("HIDDEN", "Hidden Runs"),
    ("BIP", "Defense / Batted Ball"),
    ("CTX", "Context"),
]


def safe(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def signal_color(supported_team: str | None, row_team: str) -> str:
    if supported_team is None:
        return "gray"
    return "green" if supported_team == row_team else "red"


def build_signal_map(
    event: dict[str, Any],
    schedule_game: dict[str, Any],
    rankings: dict[str, Any],
    away_pitcher: dict[str, Any],
    home_pitcher: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    away = event["away_team"]
    home = event["home_team"]

    away_profile = team_profile(rankings, schedule_game.get("away_team_id"))
    home_profile = team_profile(rankings, schedule_game.get("home_team_id"))

    sp_lean = comparative_lean(
        away_profile.get("starting_pitching", {}),
        home_profile.get("starting_pitching", {}),
        away,
        home,
    )
    lineup_lean = comparative_lean(
        away_profile.get("batting", {}),
        home_profile.get("batting", {}),
        away,
        home,
    )
    bp_lean = comparative_lean(
        away_profile.get("bullpen", {}),
        home_profile.get("bullpen", {}),
        away,
        home,
    )

    away_sp = schedule_game.get("away_probable_pitcher") or "TBD"
    home_sp = schedule_game.get("home_probable_pitcher") or "TBD"
    away_record = away_pitcher.get("record") or "N/A"
    home_record = home_pitcher.get("record") or "N/A"

    return {
        "SP": {
            "team": sp_lean.get("team"),
            "title": "Starting Pitcher Projection",
            "reason": (
                f"{away_sp} ({away_record}) vs {home_sp} ({home_record}). "
                "Current direction uses season, 30-day, and 7-day starting-pitching ranks."
            ),
            "status": "HIT" if sp_lean.get("team") else "NEUTRAL",
        },
        "MATCH": {
            "team": None,
            "title": "Starter vs Confirmed Lineup",
            "reason": "Pending official lineups and the pitch-arsenal matchup layer.",
            "status": "PENDING",
        },
        "LINEUP": {
            "team": lineup_lean.get("team"),
            "title": "Lineup Strength",
            "reason": (
                "Current direction uses batting ranks across season, last 30 days, "
                "and last 7 days. Confirmed-lineup changes are not yet applied."
            ),
            "status": "HIT" if lineup_lean.get("team") else "NEUTRAL",
        },
        "BP": {
            "team": bp_lean.get("team"),
            "title": "Bullpen Performance",
            "reason": (
                "Current direction uses bullpen performance ranks. "
                "Recent workload is shown in Game Details and will later be merged into this light."
            ),
            "status": "HIT" if bp_lean.get("team") else "NEUTRAL",
        },
        "HIDDEN": {
            "team": None,
            "title": "Hidden Runs",
            "reason": "Pending catcher framing, blocking, throwing, and baserunning inputs.",
            "status": "PENDING",
        },
        "BIP": {
            "team": None,
            "title": "Defense and Batted-Ball Fit",
            "reason": "Pending Statcast contact profiles and position-specific OAA.",
            "status": "PENDING",
        },
        "CTX": {
            "team": home,
            "title": "Situational Context",
            "reason": (
                f"Currently supports {home} for home field. "
                "Travel, rest, park fit, and roster context are not yet fully integrated."
            ),
            "status": "HIT",
        },
    }


def indicator_lights_html(signal_map: dict[str, dict[str, Any]], chosen_team: str) -> str:
    lights = []
    for index, (key, label) in enumerate(INDICATOR_LABELS, start=1):
        item = signal_map[key]
        color = signal_color(item.get("team"), chosen_team)
        lights.append(
            '<details class="top-light-wrap">'
            f'<summary class="top-light light-{safe(color)}">{index}</summary>'
            f'<div class="top-light-tip"><strong>{safe(item["title"])}</strong><br>'
            f'{safe(item["reason"])}</div></details>'
        )
    return '<div class="top-lights">' + "".join(lights) + "</div>"


def scorecard_html(
    signal_map: dict[str, dict[str, Any]],
    selected_team: str,
) -> str:
    rows = []
    for index, (key, _) in enumerate(INDICATOR_LABELS, start=1):
        item = signal_map[key]
        color = signal_color(item.get("team"), selected_team)
        if item.get("team") is None:
            label = "PENDING" if item["status"] == "PENDING" else "NEUTRAL"
        elif item.get("team") == selected_team:
            label = "HIT"
        else:
            label = "RISK"

        rows.append(
            '<div class="score-row">'
            f'<span class="score-num light-{safe(color)}">{index}</span>'
            f'<div class="score-copy"><strong>{safe(item["title"])}</strong>'
            f'<span>{safe(item["reason"])}</span></div>'
            f'<span class="score-status status-{safe(color)}">{safe(label)}</span>'
            "</div>"
        )
    return '<div class="scorecard">' + "".join(rows) + "</div>"


def _rank_value(entry: dict[str, Any]) -> str:
    rank = entry.get("rank")
    metric = entry.get("metric_value")
    metric_name = entry.get("metric_name")
    if rank is None:
        return "—"
    if metric and metric != "N/A":
        return f"#{rank} · {metric_name} {metric}"
    return f"#{rank}"


def eye_test_html(
    event: dict[str, Any],
    schedule_game: dict[str, Any],
    rankings: dict[str, Any],
    away_pitcher: dict[str, Any],
    home_pitcher: dict[str, Any],
) -> str:
    away_profile = team_profile(rankings, schedule_game.get("away_team_id"))
    home_profile = team_profile(rankings, schedule_game.get("home_team_id"))

    team_blocks = []
    for side, team_name, odds, pitcher_name, pitcher_stats, profile in [
        (
            "away",
            event["away_team"],
            event.get("best_away_odds"),
            schedule_game.get("away_probable_pitcher"),
            away_pitcher,
            away_profile,
        ),
        (
            "home",
            event["home_team"],
            event.get("best_home_odds"),
            schedule_game.get("home_probable_pitcher"),
            home_pitcher,
            home_profile,
        ),
    ]:
        record = pitcher_stats.get("record") or "N/A"
        era = pitcher_stats.get("era") or "N/A"
        rows = []
        for title, key in [
            ("Batting", "batting"),
            ("Starting Pitching", "starting_pitching"),
            ("Bullpen", "bullpen"),
        ]:
            category = profile.get(key, {})
            rows.append(
                '<div class="eye-row">'
                f'<span class="eye-label">{safe(title)}</span>'
                f'<span>{safe(_rank_value(category.get("season", {})))}</span>'
                f'<span>{safe(_rank_value(category.get("month", {})))}</span>'
                f'<span>{safe(_rank_value(category.get("week", {})))}</span>'
                f'<span>{safe(trend_label(category))}</span>'
                "</div>"
            )

        team_blocks.append(
            '<div class="eye-team">'
            f'<div class="eye-team-head"><strong>{safe(team_name)}</strong>'
            f'<span>{safe(format_moneyline(odds))}</span></div>'
            f'<div class="eye-pitcher">{safe(pitcher_name or "TBD")} · '
            f'{safe(record)} · ERA {safe(era)}</div>'
            '<div class="eye-columns"><span></span><span>Season</span>'
            '<span>30 Days</span><span>7 Days</span><span>Trend</span></div>'
            + "".join(rows)
            + "</div>"
        )

    return '<div class="eye-test-grid">' + "".join(team_blocks) + "</div>"


def winner_lean(
    signal_map: dict[str, dict[str, Any]],
    away_team: str,
    home_team: str,
) -> dict[str, Any]:
    away_count = sum(1 for item in signal_map.values() if item.get("team") == away_team)
    home_count = sum(1 for item in signal_map.values() if item.get("team") == home_team)
    pending_count = sum(1 for item in signal_map.values() if item.get("team") is None)

    if away_count > home_count:
        winner = away_team
        loser = home_team
    elif home_count > away_count:
        winner = home_team
        loser = away_team
    else:
        winner = None
        loser = None

    return {
        "winner": winner,
        "loser": loser,
        "away_count": away_count,
        "home_count": home_count,
        "pending_count": pending_count,
    }


def who_wins_html(
    event: dict[str, Any],
    signal_map: dict[str, dict[str, Any]],
) -> str:
    lean = winner_lean(signal_map, event["away_team"], event["home_team"])
    winner = lean["winner"]

    if winner:
        winner_color = "green"
        headline = f"Current Lean: {winner}"
        explanation = (
            f"{event['away_team']} {lean['away_count']} indicators · "
            f"{event['home_team']} {lean['home_count']} indicators · "
            f"{lean['pending_count']} pending/neutral."
        )
    else:
        winner_color = "gray"
        headline = "Current Lean: Too Close"
        explanation = (
            f"Both teams have {lean['away_count']} supporting indicators. "
            f"{lean['pending_count']} indicators are pending or neutral."
        )

    return (
        '<div class="winner-panel">'
        f'<div class="winner-light light-{winner_color}"></div>'
        f'<div><h3>{safe(headline)}</h3><p>{safe(explanation)}</p>'
        '<p class="winner-warning">This is a preliminary indicator count, '
        'not a trained win probability or official bet.</p></div>'
        "</div>"
        '<div class="winner-rows">'
        f'<div><strong>{safe(event["away_team"])}</strong>'
        f'<span class="status-{"green" if winner == event["away_team"] else "red" if winner else "gray"}">'
        f'{lean["away_count"]} supports</span></div>'
        f'<div><strong>{safe(event["home_team"])}</strong>'
        f'<span class="status-{"green" if winner == event["home_team"] else "red" if winner else "gray"}">'
        f'{lean["home_count"]} supports</span></div>'
        "</div>"
    )


def matchup_header_html(
    event: dict[str, Any],
    schedule_game: dict[str, Any],
    away_pitcher: dict[str, Any],
    home_pitcher: dict[str, Any],
) -> str:
    away_record = away_pitcher.get("record") or "N/A"
    home_record = home_pitcher.get("record") or "N/A"
    return (
        '<div class="matchup-header">'
        '<div class="match-team left">'
        f'<h2>{safe(event["away_team"])}</h2>'
        f'<div class="price">{safe(format_moneyline(event.get("best_away_odds")))}</div>'
        f'<div class="starter">{safe(schedule_game.get("away_probable_pitcher") or "TBD")}'
        f'<span>{safe(away_record)}</span></div></div>'
        '<div class="versus"><span>VS</span>'
        f'<small>{safe(format_game_time_et(event.get("commence_time")))}</small></div>'
        '<div class="match-team right">'
        f'<h2>{safe(event["home_team"])}</h2>'
        f'<div class="price">{safe(format_moneyline(event.get("best_home_odds")))}</div>'
        f'<div class="starter">{safe(schedule_game.get("home_probable_pitcher") or "TBD")}'
        f'<span>{safe(home_record)}</span></div></div>'
        "</div>"
    )
