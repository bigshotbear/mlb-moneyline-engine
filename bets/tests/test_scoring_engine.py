from src.scoring_engine import (
    INDICATOR_CATALOG,
    _scaled_strength,
    score_matchup,
)


def test_catalog_has_thirty_indicators():
    assert len(INDICATOR_CATALOG) == 30


def test_strength_scale():
    assert _scaled_strength(0.1, threshold=0.2, strong_at=1.0) == 0
    assert _scaled_strength(1.0, threshold=0.2, strong_at=1.0) == 100


def test_score_totals_one_hundred():
    indicators = [
        {
            "family": "starter",
            "active": True,
            "team": "A",
            "points": 5.0,
            "available": True,
            "max_points": 5.0,
            "strength": 100,
        },
        {
            "family": "offense",
            "active": True,
            "team": "B",
            "points": 3.0,
            "available": True,
            "max_points": 3.0,
            "strength": 100,
        },
    ]
    # Add empty families so score_matchup can iterate safely.
    result = score_matchup(indicators, "A", "B")
    assert round(result["away_score"] + result["home_score"], 1) == 100.0
