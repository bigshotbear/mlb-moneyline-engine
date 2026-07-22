from __future__ import annotations

from typing import Any

from .scoring_engine import evaluate_indicators, score_matchup


def adjusted_score(raw_score: float, coverage: float) -> float:
    """
    Pull incomplete raw scores back toward 50.
    85 raw with 30% coverage becomes about 60.5 instead of looking like 85%.
    """
    bounded_coverage = max(0.0, min(100.0, float(coverage)))
    return round(50.0 + (float(raw_score) - 50.0) * bounded_coverage / 100.0, 1)


def leader_reasons(
    indicators: list[dict[str, Any]],
    leader: str | None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not leader:
        return []
    return sorted(
        [
            item
            for item in indicators
            if item.get("active") and item.get("team") == leader
        ],
        key=lambda item: (item.get("points", 0), item.get("strength", 0)),
        reverse=True,
    )[:limit]


def recommendation_label(
    adjusted_leader_score: float,
    coverage: float,
    *,
    game_status: str | None = None,
) -> str:
    status_text = (game_status or "").lower()
    if any(word in status_text for word in ("progress", "inning", "live")):
        return "LIVE — OPEN IN LIVE CENTER"
    if "final" in status_text:
        return "FINAL"
    if coverage < 20:
        return "INSUFFICIENT DATA"
    if adjusted_leader_score < 53:
        return "PASS — TOO CLOSE"
    if coverage < 40:
        return "WATCH — LOW COVERAGE"
    if adjusted_leader_score >= 62 and coverage >= 60:
        return "STRONG PROVISIONAL LEAN"
    return "PROVISIONAL LEAN"


def build_ranked_entry(
    *,
    event: dict[str, Any],
    schedule_game: dict[str, Any],
    rankings: dict[str, Any],
    away_pitcher: dict[str, Any],
    home_pitcher: dict[str, Any],
    away_bullpen: dict[str, Any],
    home_bullpen: dict[str, Any],
) -> dict[str, Any]:
    indicators = evaluate_indicators(
        event=event,
        schedule_game=schedule_game,
        rankings=rankings,
        away_pitcher=away_pitcher,
        home_pitcher=home_pitcher,
        away_bullpen_workload=away_bullpen,
        home_bullpen_workload=home_bullpen,
    )
    raw = score_matchup(
        indicators,
        event["away_team"],
        event["home_team"],
    )

    away_adjusted = adjusted_score(raw["away_score"], raw["coverage"])
    home_adjusted = adjusted_score(raw["home_score"], raw["coverage"])

    if away_adjusted > home_adjusted:
        leader = event["away_team"]
        opponent = event["home_team"]
        raw_leader_score = raw["away_score"]
        adjusted_leader_score = away_adjusted
        leader_odds = event.get("best_away_odds")
    elif home_adjusted > away_adjusted:
        leader = event["home_team"]
        opponent = event["away_team"]
        raw_leader_score = raw["home_score"]
        adjusted_leader_score = home_adjusted
        leader_odds = event.get("best_home_odds")
    else:
        leader = None
        opponent = None
        raw_leader_score = 50.0
        adjusted_leader_score = 50.0
        leader_odds = None

    reasons = leader_reasons(indicators, leader, limit=5)
    top_reason_titles = [item["title"] for item in reasons[:3]]

    if leader and top_reason_titles:
        because = ", ".join(top_reason_titles[:-1])
        if len(top_reason_titles) > 1:
            because += f" and {top_reason_titles[-1]}"
        else:
            because = top_reason_titles[0]
        sentence = f"{leader} moneyline over {opponent} because of {because}."
    elif leader:
        sentence = f"{leader} moneyline over {opponent}, but the supporting data is limited."
    else:
        sentence = f"{event['away_team']} versus {event['home_team']} is too close to separate."

    label = recommendation_label(
        adjusted_leader_score,
        raw["coverage"],
        game_status=schedule_game.get("status"),
    )

    return {
        "event": event,
        "schedule_game": schedule_game,
        "indicators": indicators,
        "raw_score": raw,
        "away_adjusted_score": away_adjusted,
        "home_adjusted_score": home_adjusted,
        "leader": leader,
        "opponent": opponent,
        "leader_odds": leader_odds,
        "raw_leader_score": raw_leader_score,
        "adjusted_leader_score": adjusted_leader_score,
        "coverage": raw["coverage"],
        "reasons": reasons,
        "sentence": sentence,
        "label": label,
        "ranking_edge": round(adjusted_leader_score - 50.0, 1),
    }


def rank_slate(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda item: (
            item.get("ranking_edge", 0),
            item.get("coverage", 0),
        ),
        reverse=True,
    )
