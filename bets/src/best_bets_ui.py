from __future__ import annotations

from html import escape
from typing import Any


def safe(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def moneyline_text(value: int | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+d}"


def ranked_card_html(entry: dict[str, Any], rank: int) -> str:
    event = entry["event"]
    leader = entry.get("leader")
    label = entry.get("label", "")
    tone = (
        "strong"
        if "STRONG" in label
        else "watch"
        if "WATCH" in label or "LIVE" in label
        else "pass"
        if "PASS" in label or "INSUFFICIENT" in label
        else "lean"
    )

    reasons = "".join(
        f"<li><strong>{safe(item['title'])}</strong> — {safe(item['reason'])}</li>"
        for item in entry.get("reasons", [])[:5]
    )

    return (
        f'<div class="ranked-bet-card card-{tone}">'
        f'<div class="rank-number">#{rank}</div>'
        f'<div class="bet-card-main">'
        f'<div class="bet-label">{safe(label)}</div>'
        f'<h3>{safe(entry["sentence"])}</h3>'
        '<div class="bet-score-grid">'
        f'<span>Adjusted: <strong>{entry["adjusted_leader_score"]:.1f}</strong></span>'
        f'<span>Raw: <strong>{entry["raw_leader_score"]:.1f}</strong></span>'
        f'<span>Coverage: <strong>{entry["coverage"]:.1f}%</strong></span>'
        f'<span>Price: <strong>{safe(moneyline_text(entry.get("leader_odds")))}</strong></span>'
        '</div>'
        f'<details><summary>Top reasons</summary><ol>{reasons}</ol></details>'
        '</div></div>'
    )


def parlay_card_html(parlay: dict[str, Any]) -> str:
    odds = parlay.get("combined_odds")
    odds_text = f"{odds:+d}" if odds is not None else "N/A"
    legs_html = "".join(
        '<div class="parlay-leg">'
        f'<strong>{safe(leg["leader"])} ML '
        f'{moneyline_text(leg.get("leader_odds"))}</strong>'
        f'<span>Score {leg["adjusted_leader_score"]:.1f} · '
        f'Coverage {leg["coverage"]:.1f}%</span></div>'
        for leg in parlay.get("legs", [])
    )
    weakest = parlay.get("weakest_leg") or {}
    return (
        '<div class="parlay-card">'
        f'<div><span class="parlay-name">{safe(parlay["name"])}</span>'
        f'<strong class="parlay-price">{safe(odds_text)}</strong></div>'
        f'{legs_html}'
        f'<div class="weakest-leg">Weakest leg: {safe(weakest.get("leader", "N/A"))}</div>'
        '</div>'
    )
