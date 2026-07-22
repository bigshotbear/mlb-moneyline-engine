from __future__ import annotations

from html import escape
from statistics import mean
from typing import Any

from .team_rankings import team_profile, trend_label
from .ui_helpers import format_game_time_et, format_moneyline


def safe(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def _number(value: Any) -> float | None:
    if value in (None, "", "N/A", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rank(entry: dict[str, Any]) -> float | None:
    value = entry.get("rank")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _winner_lower(
    away_value: float | None,
    home_value: float | None,
    away_team: str,
    home_team: str,
    deadband: float,
) -> str | None:
    if away_value is None or home_value is None:
        return None
    difference = home_value - away_value
    if abs(difference) < deadband:
        return None
    return away_team if away_value < home_value else home_team


def _winner_higher(
    away_value: float | None,
    home_value: float | None,
    away_team: str,
    home_team: str,
    deadband: float,
) -> str | None:
    if away_value is None or home_value is None:
        return None
    difference = away_value - home_value
    if abs(difference) < deadband:
        return None
    return away_team if away_value > home_value else home_team


def _win_pct(stats: dict[str, Any]) -> float | None:
    wins = _number(stats.get("wins"))
    losses = _number(stats.get("losses"))
    if wins is None or losses is None or wins + losses < 5:
        return None
    return wins / (wins + losses)


def _ratio(stats: dict[str, Any]) -> float | None:
    direct = _number(stats.get("strikeout_walk_ratio"))
    if direct is not None:
        return direct
    strikeouts = _number(stats.get("strikeouts"))
    walks = _number(stats.get("walks"))
    if strikeouts is None or walks is None or walks <= 0:
        return None
    return strikeouts / walks


def _average_rank(category: dict[str, Any], windows: tuple[str, ...]) -> float | None:
    values = [_rank(category.get(window, {})) for window in windows]
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    return mean(usable)


def _rank_reason(
    category_name: str,
    away_category: dict[str, Any],
    home_category: dict[str, Any],
    window: str,
    away_team: str,
    home_team: str,
) -> str:
    away_entry = away_category.get(window, {})
    home_entry = home_category.get(window, {})
    label = {"season": "season", "month": "last 30 days", "week": "last 7 days"}[window]
    return (
        f"{category_name} {label}: {away_team} rank "
        f"#{away_entry.get('rank', '—')} vs {home_team} rank "
        f"#{home_entry.get('rank', '—')}."
    )


def build_active_signals(
    event: dict[str, Any],
    schedule_game: dict[str, Any],
    rankings: dict[str, Any],
    away_pitcher: dict[str, Any],
    home_pitcher: dict[str, Any],
    away_bullpen_workload: dict[str, Any] | None = None,
    home_bullpen_workload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Build descriptive eye-test signals from currently available data.

    Neutral/unavailable signals are returned with active=False so the interface
    can hide them instead of filling the scorecard with pending gray rows.
    """
    away = event["away_team"]
    home = event["home_team"]

    away_profile = team_profile(rankings, schedule_game.get("away_team_id"))
    home_profile = team_profile(rankings, schedule_game.get("home_team_id"))

    away_batting = away_profile.get("batting", {})
    home_batting = home_profile.get("batting", {})
    away_sp_staff = away_profile.get("starting_pitching", {})
    home_sp_staff = home_profile.get("starting_pitching", {})
    away_bp = away_profile.get("bullpen", {})
    home_bp = home_profile.get("bullpen", {})

    signals: list[dict[str, Any]] = []

    def add(
        key: str,
        title: str,
        team: str | None,
        reason: str,
        group: str,
        supporting_only: bool = False,
    ) -> None:
        signals.append(
            {
                "key": key,
                "title": title,
                "team": team,
                "reason": reason,
                "group": group,
                "supporting_only": supporting_only,
                "active": team is not None,
            }
        )

    away_era = _number(away_pitcher.get("era"))
    home_era = _number(home_pitcher.get("era"))
    add(
        "starter_era",
        "Starter ERA Edge",
        _winner_lower(away_era, home_era, away, home, 0.25),
        f"Starter ERA: {away} {away_era if away_era is not None else '—'} vs "
        f"{home} {home_era if home_era is not None else '—'}. "
        "A difference smaller than 0.25 is treated as neutral.",
        "Starting Pitcher",
    )

    away_whip = _number(away_pitcher.get("whip"))
    home_whip = _number(home_pitcher.get("whip"))
    add(
        "starter_whip",
        "Starter WHIP Edge",
        _winner_lower(away_whip, home_whip, away, home, 0.03),
        f"Starter WHIP: {away} {away_whip if away_whip is not None else '—'} vs "
        f"{home} {home_whip if home_whip is not None else '—'}.",
        "Starting Pitcher",
    )

    away_ratio = _ratio(away_pitcher)
    home_ratio = _ratio(home_pitcher)
    add(
        "starter_kbb",
        "Starter K/BB Edge",
        _winner_higher(away_ratio, home_ratio, away, home, 0.20),
        f"Starter strikeout-to-walk ratio: {away} "
        f"{round(away_ratio, 2) if away_ratio is not None else '—'} vs {home} "
        f"{round(home_ratio, 2) if home_ratio is not None else '—'}.",
        "Starting Pitcher",
    )

    away_win_pct = _win_pct(away_pitcher)
    home_win_pct = _win_pct(home_pitcher)
    add(
        "starter_record",
        "Starter Record Context",
        _winner_higher(away_win_pct, home_win_pct, away, home, 0.10),
        f"Pitcher decision win rate: {away} "
        f"{round(away_win_pct * 100, 1) if away_win_pct is not None else '—'}% vs "
        f"{home} {round(home_win_pct * 100, 1) if home_win_pct is not None else '—'}%. "
        "This is supporting context only because pitcher records depend heavily on team support.",
        "Starting Pitcher",
        supporting_only=True,
    )

    for key, title, window in (
        ("offense_season", "Season Offense", "season"),
        ("offense_30", "30-Day Offense", "month"),
        ("offense_7", "7-Day Offense", "week"),
    ):
        away_value = _rank(away_batting.get(window, {}))
        home_value = _rank(home_batting.get(window, {}))
        add(
            key,
            title,
            _winner_lower(away_value, home_value, away, home, 3.0),
            _rank_reason("Batting", away_batting, home_batting, window, away, home),
            "Offense",
        )

    away_sp_season = _rank(away_sp_staff.get("season", {}))
    home_sp_season = _rank(home_sp_staff.get("season", {}))
    add(
        "sp_staff_season",
        "Season Starting-Pitching Staff",
        _winner_lower(away_sp_season, home_sp_season, away, home, 3.0),
        _rank_reason(
            "Starting pitching",
            away_sp_staff,
            home_sp_staff,
            "season",
            away,
            home,
        ),
        "Team Pitching",
    )

    away_sp_recent = _average_rank(away_sp_staff, ("month", "week"))
    home_sp_recent = _average_rank(home_sp_staff, ("month", "week"))
    add(
        "sp_staff_recent",
        "Recent Starting-Pitching Form",
        _winner_lower(away_sp_recent, home_sp_recent, away, home, 3.0),
        f"Average starting-pitching rank over the last 30 and 7 days: "
        f"{away} {round(away_sp_recent, 1) if away_sp_recent is not None else '—'} vs "
        f"{home} {round(home_sp_recent, 1) if home_sp_recent is not None else '—'}.",
        "Team Pitching",
    )

    away_bp_season = _rank(away_bp.get("season", {}))
    home_bp_season = _rank(home_bp.get("season", {}))
    add(
        "bullpen_season",
        "Season Bullpen",
        _winner_lower(away_bp_season, home_bp_season, away, home, 3.0),
        _rank_reason("Bullpen", away_bp, home_bp, "season", away, home),
        "Bullpen",
    )

    away_bp_recent = _average_rank(away_bp, ("month", "week"))
    home_bp_recent = _average_rank(home_bp, ("month", "week"))
    add(
        "bullpen_recent",
        "Recent Bullpen Form",
        _winner_lower(away_bp_recent, home_bp_recent, away, home, 3.0),
        f"Average bullpen rank over the last 30 and 7 days: "
        f"{away} {round(away_bp_recent, 1) if away_bp_recent is not None else '—'} vs "
        f"{home} {round(home_bp_recent, 1) if home_bp_recent is not None else '—'}.",
        "Bullpen",
    )

    away_workload = (
        (away_bullpen_workload or {}).get("summary", {}).get("pitches_3d")
    )
    home_workload = (
        (home_bullpen_workload or {}).get("summary", {}).get("pitches_3d")
    )
    away_workload_num = _number(away_workload)
    home_workload_num = _number(home_workload)
    add(
        "bullpen_workload",
        "Bullpen Workload",
        _winner_lower(
            away_workload_num,
            home_workload_num,
            away,
            home,
            20.0,
        ),
        f"Relief pitches over the previous three days: {away} "
        f"{int(away_workload_num) if away_workload_num is not None else '—'} vs "
        f"{home} {int(home_workload_num) if home_workload_num is not None else '—'}. "
        "At least a 20-pitch difference is required.",
        "Bullpen",
    )

    add(
        "home_field",
        "Home Field",
        home,
        f"{home} receives the home-field supporting signal.",
        "Context",
        supporting_only=True,
    )

    return signals


def visible_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [signal for signal in signals if signal.get("active")]


def signal_color(supported_team: str | None, perspective_team: str) -> str:
    if supported_team is None:
        return "gray"
    return "green" if supported_team == perspective_team else "red"


def indicator_lights_html(
    signals: list[dict[str, Any]],
    perspective_team: str,
) -> str:
    visible = visible_signals(signals)
    lights: list[str] = []

    for index, signal in enumerate(visible, start=1):
        color = signal_color(signal.get("team"), perspective_team)
        supporting_note = (
            "<br><em>Supporting context only.</em>"
            if signal.get("supporting_only")
            else ""
        )
        lights.append(
            '<details class="top-light-wrap">'
            f'<summary class="top-light light-{safe(color)}">{index}</summary>'
            f'<div class="top-light-tip"><strong>{safe(signal["title"])}</strong><br>'
            f'{safe(signal["reason"])}{supporting_note}</div></details>'
        )

    if not lights:
        return '<div class="empty-signals">No active data edges yet.</div>'

    return (
        '<div class="signal-strip-scroll"><div class="top-lights">'
        + "".join(lights)
        + "</div></div>"
    )


def scorecard_html(
    signals: list[dict[str, Any]],
    selected_team: str,
) -> str:
    rows: list[str] = []
    visible = visible_signals(signals)

    for index, signal in enumerate(visible, start=1):
        color = signal_color(signal.get("team"), selected_team)
        label = "HIT" if color == "green" else "RISK"
        context_badge = (
            '<span class="supporting-badge">CONTEXT</span>'
            if signal.get("supporting_only")
            else ""
        )
        rows.append(
            '<div class="score-row">'
            f'<span class="score-num light-{safe(color)}">{index}</span>'
            f'<div class="score-copy"><strong>{safe(signal["title"])}'
            f'{context_badge}</strong><span>{safe(signal["reason"])}</span></div>'
            f'<span class="score-status status-{safe(color)}">{label}</span>'
            "</div>"
        )

    if not rows:
        return '<div class="empty-signals">No active signals for this matchup yet.</div>'

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
    for team_name, odds, pitcher_name, pitcher_stats, profile in [
        (
            event["away_team"],
            event.get("best_away_odds"),
            schedule_game.get("away_probable_pitcher"),
            away_pitcher,
            away_profile,
        ),
        (
            event["home_team"],
            event.get("best_home_odds"),
            schedule_game.get("home_probable_pitcher"),
            home_pitcher,
            home_profile,
        ),
    ]:
        record = pitcher_stats.get("record") or "N/A"
        era = pitcher_stats.get("era") or "N/A"
        whip = pitcher_stats.get("whip") or "N/A"
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
            f'{safe(record)} · ERA {safe(era)} · WHIP {safe(whip)}</div>'
            '<div class="eye-columns"><span></span><span>Season</span>'
            '<span>30 Days</span><span>7 Days</span><span>Trend</span></div>'
            + "".join(rows)
            + "</div>"
        )

    return '<div class="eye-test-grid">' + "".join(team_blocks) + "</div>"


def count_support(
    signals: list[dict[str, Any]],
    team: str,
    *,
    include_supporting: bool = True,
) -> int:
    return sum(
        1
        for signal in visible_signals(signals)
        if signal.get("team") == team
        and (include_supporting or not signal.get("supporting_only"))
    )



def winner_lean(
    signals: dict[str, dict[str, Any]] | list[dict[str, Any]],
    away_team: str,
    home_team: str,
) -> dict[str, Any]:
    """Backward-compatible support counter used by earlier tests and snapshots."""
    if isinstance(signals, dict):
        normalized = [
            {
                **value,
                "active": value.get("team") is not None,
                "supporting_only": value.get("supporting_only", False),
            }
            for value in signals.values()
        ]
    else:
        normalized = signals

    away_count = count_support(normalized, away_team)
    home_count = count_support(normalized, home_team)
    pending_count = sum(
        1 for signal in normalized if signal.get("team") is None
    )

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
    signals: list[dict[str, Any]],
) -> str:
    away = event["away_team"]
    home = event["home_team"]
    away_count = count_support(signals, away)
    home_count = count_support(signals, home)
    active_count = len(visible_signals(signals))

    if away_count > home_count:
        winner = away
    elif home_count > away_count:
        winner = home
    else:
        winner = None

    if winner:
        headline = f"Current Lean: {winner}"
        color = "green"
    else:
        headline = "Current Lean: Too Close"
        color = "gray"

    return (
        '<div class="winner-panel">'
        f'<div class="winner-light light-{color}"></div>'
        f'<div><h3>{safe(headline)}</h3>'
        f'<p>{safe(away)} {away_count} supports · '
        f'{safe(home)} {home_count} supports · {active_count} active signals.</p>'
        '<p class="winner-warning">This is an eye-test signal count, not a trained '
        'win probability or official bet.</p></div></div>'
        '<div class="winner-rows">'
        f'<div><strong>{safe(away)}</strong><span class="status-'
        f'{"green" if winner == away else "red" if winner else "gray"}">'
        f'{away_count} supports</span></div>'
        f'<div><strong>{safe(home)}</strong><span class="status-'
        f'{"green" if winner == home else "red" if winner else "gray"}">'
        f'{home_count} supports</span></div></div>'
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
