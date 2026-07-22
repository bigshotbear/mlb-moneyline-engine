from __future__ import annotations

from html import escape
from typing import Any


def safe(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def strength_color(strength: float) -> str:
    if strength >= 70:
        return "strong"
    if strength >= 40:
        return "medium"
    return "light"


def matchup_score_html(score: dict[str, Any]) -> str:
    away = score["away_team"]
    home = score["home_team"]
    away_score = score["away_score"]
    home_score = score["home_score"]
    coverage = score["coverage"]
    leader = score["leader"] or "Too Close"

    return (
        '<div class="final-score-card">'
        '<div class="score-kicker">PROVISIONAL MATCHUP SCORE</div>'
        f'<div class="score-leader">Current Lean: {safe(leader)}</div>'
        '<div class="team-score-grid">'
        f'<div><strong>{safe(away)}</strong><span>{away_score:.1f}</span></div>'
        f'<div><strong>{safe(home)}</strong><span>{home_score:.1f}</span></div>'
        '</div>'
        '<div class="score-track">'
        f'<div class="score-away" style="width:{away_score}%"></div>'
        f'<div class="score-home" style="width:{home_score}%"></div>'
        '</div>'
        f'<div class="coverage-line">Data coverage: {coverage:.1f}% · '
        f'{score["available_count"]}/{score["total_count"]} indicators available · '
        f'{score["active_count"]} active edges</div>'
        '<div class="score-disclaimer">This is a relative matchup score, not a '
        'validated win probability.</div>'
        '</div>'
    )


def top_five_html(
    score: dict[str, Any],
    perspective_team: str,
) -> str:
    rows = []
    for rank, item in enumerate(score["top_five"], start=1):
        supports_selected = item.get("team") == perspective_team
        color = "green" if supports_selected else "red"
        strength = item.get("strength", 0.0)
        strength_class = strength_color(strength)
        context = (
            '<span class="context-chip">CONTEXT</span>'
            if item.get("supporting_only")
            else ""
        )
        rows.append(
            '<div class="top-reason-row">'
            f'<span class="reason-rank">{rank}</span>'
            f'<span class="reason-dot reason-{color}"></span>'
            '<div class="reason-copy">'
            f'<strong>{safe(item["title"])}{context}</strong>'
            f'<span>{safe(item["reason"])}</span>'
            '<div class="strength-track">'
            f'<div class="strength-fill strength-{strength_class}" '
            f'style="width:{strength}%"></div></div>'
            '</div>'
            f'<div class="strength-number">{strength:.0f}<small>/100</small></div>'
            '</div>'
        )

    if not rows:
        return '<div class="empty-signals">No active scored indicators.</div>'

    return '<div class="top-five-card">' + "".join(rows) + "</div>"


def all_indicators_rows(indicators: list[dict[str, Any]], perspective_team: str) -> list[dict[str, Any]]:
    rows = []
    for item in indicators:
        if not item.get("available"):
            status = "Not connected"
        elif not item.get("active"):
            status = "Neutral"
        elif item.get("team") == perspective_team:
            status = "Supports selected"
        else:
            status = "Supports opponent"

        rows.append(
            {
                "Indicator": item["title"],
                "Family": item["family"].replace("_", " ").title(),
                "Status": status,
                "Strength": item["strength"],
                "Max Points": item["max_points"],
                "Weighted Points": item["points"],
                "Supports": item.get("team") or "—",
                "Reason": item["reason"],
            }
        )
    return rows
