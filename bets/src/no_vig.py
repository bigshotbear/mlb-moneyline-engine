from __future__ import annotations

from dataclasses import dataclass


class OddsError(ValueError):
    pass


def american_to_decimal(american_odds: int | float) -> float:
    odds = float(american_odds)
    if odds == 0:
        raise OddsError("American odds cannot be zero.")
    if odds > 0:
        return 1.0 + (odds / 100.0)
    return 1.0 + (100.0 / abs(odds))


def american_to_implied_probability(american_odds: int | float) -> float:
    odds = float(american_odds)
    if odds == 0:
        raise OddsError("American odds cannot be zero.")
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


@dataclass(frozen=True)
class NoVigPair:
    side_a_probability: float
    side_b_probability: float
    overround: float


def remove_vig_two_way(
    side_a_odds: int | float,
    side_b_odds: int | float,
) -> NoVigPair:
    raw_a = american_to_implied_probability(side_a_odds)
    raw_b = american_to_implied_probability(side_b_odds)
    total = raw_a + raw_b
    if total <= 0:
        raise OddsError("The implied probability total must be positive.")

    return NoVigPair(
        side_a_probability=raw_a / total,
        side_b_probability=raw_b / total,
        overround=total - 1.0,
    )


def expected_value(model_probability: float, american_odds: int | float) -> float:
    if not 0.0 <= model_probability <= 1.0:
        raise ValueError("model_probability must be between 0 and 1.")
    return model_probability * american_to_decimal(american_odds) - 1.0
