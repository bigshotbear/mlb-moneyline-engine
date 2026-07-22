from __future__ import annotations

from math import prod
from typing import Any


def american_to_decimal(odds: int | float) -> float:
    value = float(odds)
    if value > 0:
        return 1.0 + value / 100.0
    return 1.0 + 100.0 / abs(value)


def decimal_to_american(decimal_odds: float) -> int:
    if decimal_odds <= 1:
        raise ValueError("Decimal odds must be greater than 1.")
    if decimal_odds >= 2:
        return round((decimal_odds - 1.0) * 100.0)
    return round(-100.0 / (decimal_odds - 1.0))


def combined_american_odds(entries: list[dict[str, Any]]) -> int | None:
    prices = [entry.get("leader_odds") for entry in entries]
    if not prices or any(price is None for price in prices):
        return None
    decimal = prod(american_to_decimal(price) for price in prices)
    return decimal_to_american(decimal)


def eligible_entries(
    ranked_entries: list[dict[str, Any]],
    *,
    min_adjusted_score: float,
    min_coverage: float,
) -> list[dict[str, Any]]:
    return [
        entry
        for entry in ranked_entries
        if entry.get("leader")
        and entry.get("leader_odds") is not None
        and entry.get("adjusted_leader_score", 0) >= min_adjusted_score
        and entry.get("coverage", 0) >= min_coverage
        and "LIVE" not in entry.get("label", "")
        and entry.get("label") != "FINAL"
    ]


def suggested_parlays(
    ranked_entries: list[dict[str, Any]],
    *,
    min_adjusted_score: float = 56.0,
    min_coverage: float = 30.0,
) -> list[dict[str, Any]]:
    eligible = eligible_entries(
        ranked_entries,
        min_adjusted_score=min_adjusted_score,
        min_coverage=min_coverage,
    )
    suggestions: list[dict[str, Any]] = []

    if len(eligible) >= 2:
        legs = eligible[:2]
        suggestions.append(
            {
                "name": "Top 2-Leg",
                "legs": legs,
                "combined_odds": combined_american_odds(legs),
                "weakest_leg": min(
                    legs,
                    key=lambda item: (
                        item["adjusted_leader_score"],
                        item["coverage"],
                    ),
                ),
            }
        )

    if len(eligible) >= 3:
        legs = eligible[:3]
        suggestions.append(
            {
                "name": "Top 3-Leg",
                "legs": legs,
                "combined_odds": combined_american_odds(legs),
                "weakest_leg": min(
                    legs,
                    key=lambda item: (
                        item["adjusted_leader_score"],
                        item["coverage"],
                    ),
                ),
            }
        )

    plus_money = [entry for entry in eligible if (entry.get("leader_odds") or 0) > 0]
    if plus_money and len(eligible) >= 2:
        value_leg = plus_money[0]
        partner = next(
            (entry for entry in eligible if entry is not value_leg),
            None,
        )
        if partner:
            legs = [value_leg, partner]
            suggestions.append(
                {
                    "name": "Value 2-Leg",
                    "legs": legs,
                    "combined_odds": combined_american_odds(legs),
                    "weakest_leg": min(
                        legs,
                        key=lambda item: (
                            item["adjusted_leader_score"],
                            item["coverage"],
                        ),
                    ),
                }
            )

    return suggestions
