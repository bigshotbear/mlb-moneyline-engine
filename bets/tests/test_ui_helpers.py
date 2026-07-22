from src.ui_helpers import format_game_time_et, format_moneyline


def test_moneyline_format():
    assert format_moneyline(120) == "+120"
    assert format_moneyline(-135) == "-135"


def test_time_format_is_not_military():
    result = format_game_time_et("2026-07-22T17:06:00Z")
    assert "1:06 PM ET" in result
