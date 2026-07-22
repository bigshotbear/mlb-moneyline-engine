from src.team_rankings import comparative_lean, trend_label


def test_hot_trend():
    profile = {
        "season": {"rank": 20},
        "month": {"rank": 10},
        "week": {"rank": 5},
    }
    assert trend_label(profile) == "🔥 Hot"


def test_comparative_lean():
    away = {
        "season": {"rank": 5},
        "month": {"rank": 6},
        "week": {"rank": 4},
    }
    home = {
        "season": {"rank": 18},
        "month": {"rank": 15},
        "week": {"rank": 20},
    }
    result = comparative_lean(away, home, "Away", "Home")
    assert result["team"] == "Away"
