from src.matchup_dashboard import (
    count_support,
    signal_color,
    visible_signals,
)


def test_hidden_neutral_signals():
    signals = [
        {"team": "A", "active": True},
        {"team": None, "active": False},
        {"team": "B", "active": True},
    ]
    assert len(visible_signals(signals)) == 2


def test_support_counts_only_visible():
    signals = [
        {"team": "A", "active": True, "supporting_only": False},
        {"team": "A", "active": False, "supporting_only": False},
        {"team": "B", "active": True, "supporting_only": False},
    ]
    assert count_support(signals, "A") == 1


def test_colors():
    assert signal_color("A", "A") == "green"
    assert signal_color("A", "B") == "red"
