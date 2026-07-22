from src.matchup_dashboard import signal_color, winner_lean


def test_signal_colors():
    assert signal_color("A", "A") == "green"
    assert signal_color("A", "B") == "red"
    assert signal_color(None, "A") == "gray"


def test_winner_lean():
    signals = {
        "1": {"team": "A"},
        "2": {"team": "A"},
        "3": {"team": "B"},
        "4": {"team": None},
    }
    result = winner_lean(signals, "A", "B")
    assert result["winner"] == "A"
    assert result["away_count"] == 2
    assert result["home_count"] == 1
    assert result["pending_count"] == 1
