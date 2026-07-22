from __future__ import annotations

from html import escape
from typing import Any

from .team_rankings import comparative_lean, team_profile, trend_label
from .ui_helpers import format_game_time_et, format_moneyline


INDICATORS = [
    ("SP", "Starting-pitcher projection"),
    ("MATCH", "Starter vs confirmed lineup"),
    ("LINEUP", "Confirmed-lineup strength"),
    ("BP", "Bullpen asymmetry"),
    ("HIDDEN", "Catching, baserunning, and hidden runs"),
    ("BIP", "Batted-ball and defensive interaction"),
    ("CTX", "Situational and roster context"),
]


def _safe(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def _rank_short(entry: dict[str, Any]) -> str:
    rank = entry.get("rank")
    if rank is None:
        return "—"
    return f"#{rank}"


def _rank_tooltip(entry: dict[str, Any], label: str) -> str:
    rank = entry.get("rank")
    metric_name = entry.get("metric_name")
    metric_value = entry.get("metric_value")
    if rank is None:
        return f"{label}: data unavailable"
    metric = ""
    if metric_name and metric_value and metric_value != "N/A":
        metric = f", {metric_name} {metric_value}"
    return f"{label}: MLB rank #{rank}{metric}"


def _trend_icon(category: dict[str, Any]) -> tuple[str, str]:
    label = trend_label(category)
    if "Hot" in label:
        return "🔥", "Hot: last-7-day rank is at least five places better than season rank."
    if "Cooling" in label:
        return "🧊", "Cooling: last-7-day rank is at least five places worse than season rank."
    if "Steady" in label:
        return "➖", "Steady: last-7-day rank is within four places of season rank."
    return "·", "Trend data unavailable."


def _rank_strip(category: dict[str, Any], category_name: str) -> str:
    season = category.get("season", {})
    month = category.get("month", {})
    week = category.get("week", {})
    icon, trend_tip = _trend_icon(category)

    tooltip = " | ".join(
        [
            _rank_tooltip(season, f"{category_name} season"),
            _rank_tooltip(month, f"{category_name} last 30 days"),
            _rank_tooltip(week, f"{category_name} last 7 days"),
            trend_tip,
        ]
    )

    return (
        f'<span class="rank-strip" title="{_safe(tooltip)}">'
        f'<span class="window-tag">S {_safe(_rank_short(season))}</span>'
        f'<span class="window-tag">30 {_safe(_rank_short(month))}</span>'
        f'<span class="window-tag">7 {_safe(_rank_short(week))}</span>'
        f'<span class="trend-icon">{icon}</span>'
        f"</span>"
    )


def _signal(
    color: str,
    tooltip: str,
    label: str,
) -> str:
    # details/summary provides tap-to-open on mobile. CSS provides hover on desktop.
    return (
        '<details class="signal-wrap">'
        f'<summary class="signal signal-{_safe(color)}" '
        f'aria-label="{_safe(label)}" title="{_safe(tooltip)}"></summary>'
        f'<div class="signal-tip"><strong>{_safe(label)}</strong><br>{_safe(tooltip)}</div>'
        "</details>"
    )


def _color_for_team(
    supported_team: str | None,
    row_team: str,
) -> str:
    if supported_team is None:
        return "gray"
    return "green" if supported_team == row_team else "red"


def _pitcher_line(
    pitcher_name: str | None,
    pitcher_stats: dict[str, Any],
) -> str:
    name = pitcher_name or "TBD"
    if not pitcher_stats.get("available"):
        return f"<strong>{_safe(name)}</strong><span class='subline'>Record unavailable</span>"

    record = pitcher_stats.get("record") or "N/A"
    era = pitcher_stats.get("era") or "N/A"
    return (
        f"<strong>{_safe(name)}</strong>"
        f"<span class='subline'>{_safe(record)} • ERA {_safe(era)}</span>"
    )


def _indicator_values(
    event: dict[str, Any],
    schedule_game: dict[str, Any],
    rankings: dict[str, Any],
    away_pitcher: dict[str, Any],
    home_pitcher: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    away_name = event["away_team"]
    home_name = event["home_team"]
    away_profile = team_profile(rankings, schedule_game.get("away_team_id"))
    home_profile = team_profile(rankings, schedule_game.get("home_team_id"))

    starter_lean = comparative_lean(
        away_profile.get("starting_pitching", {}),
        home_profile.get("starting_pitching", {}),
        away_name,
        home_name,
    )
    lineup_lean = comparative_lean(
        away_profile.get("batting", {}),
        home_profile.get("batting", {}),
        away_name,
        home_name,
    )
    bullpen_lean = comparative_lean(
        away_profile.get("bullpen", {}),
        home_profile.get("bullpen", {}),
        away_name,
        home_name,
    )

    away_starter = schedule_game.get("away_probable_pitcher") or "TBD"
    home_starter = schedule_game.get("home_probable_pitcher") or "TBD"
    away_record = away_pitcher.get("record") or "N/A"
    home_record = home_pitcher.get("record") or "N/A"

    return {
        "SP": {
            "team": starter_lean.get("team"),
            "reason": (
                f"Preliminary direction from season, 30-day, and 7-day team starting-pitching ranks. "
                f"{away_starter} ({away_record}) vs {home_starter} ({home_record})."
            ),
        },
        "MATCH": {
            "team": None,
            "reason": (
                "Gray until both official lineups and the pitch-arsenal matchup layer are available."
            ),
        },
        "LINEUP": {
            "team": lineup_lean.get("team"),
            "reason": (
                "Preliminary direction from team batting ranks across season, last 30 days, "
                "and last 7 days. Confirmed-lineup adjustments are not yet applied."
            ),
        },
        "BP": {
            "team": bullpen_lean.get("team"),
            "reason": (
                "Preliminary direction from bullpen performance ranks. "
                "Recent pitch workload is available in Game Details and will later be integrated here."
            ),
        },
        "HIDDEN": {
            "team": None,
            "reason": (
                "Gray until catcher framing, blocking, throwing, and baserunning data are integrated."
            ),
        },
        "BIP": {
            "team": None,
            "reason": (
                "Gray until Statcast batted-ball profiles and position-specific OAA are integrated."
            ),
        },
        "CTX": {
            "team": home_name,
            "reason": (
                f"Currently reflects home field only, supporting {home_name}. "
                "Travel, rest, park fit, and roster context are not yet included."
            ),
        },
    }


def render_indicator_board(
    *,
    events: list[dict[str, Any]],
    matched_games: dict[str, dict[str, Any] | None],
    rankings_by_date: dict[Any, dict[str, Any]],
    pitcher_cache: dict[tuple[int | None, int], dict[str, Any]],
    event_date_func,
) -> str:
    header_cells = "".join(
        f'<th title="{_safe(full_name)}">{_safe(short_name)}</th>'
        for short_name, full_name in INDICATORS
    )

    rows: list[str] = []

    for event in events:
        event_key = event.get("event_id") or event.get("commence_time")
        schedule_game = matched_games.get(event_key)
        if not schedule_game:
            continue

        game_date = event_date_func(event.get("commence_time"))
        rankings = rankings_by_date.get(game_date, {"windows": {}})
        season = game_date.year

        away_pitcher = pitcher_cache.get(
            (schedule_game.get("away_probable_pitcher_id"), season),
            {"available": False},
        )
        home_pitcher = pitcher_cache.get(
            (schedule_game.get("home_probable_pitcher_id"), season),
            {"available": False},
        )

        signals = _indicator_values(
            event,
            schedule_game,
            rankings,
            away_pitcher,
            home_pitcher,
        )

        time_text = format_game_time_et(event.get("commence_time"))
        rows.append(
            f'<tr class="game-divider"><td colspan="10">'
            f'<span class="game-time">{_safe(time_text)}</span>'
            f'<strong>{_safe(event["away_team"])} at {_safe(event["home_team"])}</strong>'
            "</td></tr>"
        )

        team_rows = [
            (
                event["away_team"],
                event.get("best_away_odds"),
                schedule_game.get("away_probable_pitcher"),
                away_pitcher,
            ),
            (
                event["home_team"],
                event.get("best_home_odds"),
                schedule_game.get("home_probable_pitcher"),
                home_pitcher,
            ),
        ]

        for team_name, odds, pitcher_name, pitcher_stats in team_rows:
            signal_cells = []
            for short_name, full_name in INDICATORS:
                item = signals[short_name]
                color = _color_for_team(item.get("team"), team_name)
                signal_cells.append(
                    f"<td class='signal-cell'>"
                    f"{_signal(color, item['reason'], full_name)}"
                    "</td>"
                )

            rows.append(
                "<tr class='team-signal-row'>"
                f"<td class='team-cell'><strong>{_safe(team_name)}</strong>"
                f"<span class='subline'>{_safe(format_moneyline(odds))}</span></td>"
                f"<td class='pitcher-cell'>{_pitcher_line(pitcher_name, pitcher_stats)}</td>"
                + "".join(signal_cells)
                + "</tr>"
            )

    return (
        '<div class="board-help">'
        "<span class='legend-dot legend-green'></span> supports team "
        "<span class='legend-dot legend-gray'></span> neutral/pending "
        "<span class='legend-dot legend-red'></span> supports opponent "
        "<span class='tap-note'>Hover on desktop or tap a light on mobile for the reason.</span>"
        "</div>"
        '<div class="board-scroll">'
        '<table class="indicator-board">'
        "<thead><tr><th>TEAM</th><th>STARTER</th>"
        f"{header_cells}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table></div>"
    )


def render_eye_test_board(
    *,
    events: list[dict[str, Any]],
    matched_games: dict[str, dict[str, Any] | None],
    rankings_by_date: dict[Any, dict[str, Any]],
    pitcher_cache: dict[tuple[int | None, int], dict[str, Any]],
    event_date_func,
) -> str:
    rows: list[str] = []

    for event in events:
        event_key = event.get("event_id") or event.get("commence_time")
        schedule_game = matched_games.get(event_key)
        if not schedule_game:
            continue

        game_date = event_date_func(event.get("commence_time"))
        rankings = rankings_by_date.get(game_date, {"windows": {}})
        season = game_date.year
        time_text = format_game_time_et(event.get("commence_time"))

        rows.append(
            f'<tr class="game-divider"><td colspan="6">'
            f'<span class="game-time">{_safe(time_text)}</span>'
            f'<strong>{_safe(event["away_team"])} at {_safe(event["home_team"])}</strong>'
            "</td></tr>"
        )

        team_rows = [
            (
                event["away_team"],
                event.get("best_away_odds"),
                schedule_game.get("away_probable_pitcher"),
                pitcher_cache.get(
                    (schedule_game.get("away_probable_pitcher_id"), season),
                    {"available": False},
                ),
                team_profile(rankings, schedule_game.get("away_team_id")),
            ),
            (
                event["home_team"],
                event.get("best_home_odds"),
                schedule_game.get("home_probable_pitcher"),
                pitcher_cache.get(
                    (schedule_game.get("home_probable_pitcher_id"), season),
                    {"available": False},
                ),
                team_profile(rankings, schedule_game.get("home_team_id")),
            ),
        ]

        for team_name, odds, pitcher_name, pitcher_stats, profile in team_rows:
            rows.append(
                "<tr class='eye-team-row'>"
                f"<td class='team-cell'><strong>{_safe(team_name)}</strong>"
                f"<span class='subline'>{_safe(format_moneyline(odds))}</span></td>"
                f"<td class='pitcher-cell'>{_pitcher_line(pitcher_name, pitcher_stats)}</td>"
                f"<td>{_rank_strip(profile.get('batting', {}), 'Batting')}</td>"
                f"<td>{_rank_strip(profile.get('starting_pitching', {}), 'Starting pitching')}</td>"
                f"<td>{_rank_strip(profile.get('bullpen', {}), 'Bullpen')}</td>"
                f"<td class='market-cell'>{_safe(event.get('consensus_away_no_vig') if team_name == event['away_team'] else event.get('consensus_home_no_vig'))}</td>"
                "</tr>"
            )

    return (
        '<div class="eye-help">'
        "Ranks read <strong>S</strong>eason / last <strong>30</strong> days / last <strong>7</strong> days. "
        "Hover a rank group for the underlying OPS or ERA."
        "</div>"
        '<div class="board-scroll">'
        '<table class="eye-board">'
        "<thead><tr>"
        "<th>TEAM</th><th>STARTER</th><th>BATTING</th>"
        "<th>STARTING PITCHING</th><th>BULLPEN</th><th>MARKET</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table></div>"
    )
