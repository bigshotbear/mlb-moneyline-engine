from src.board_ui import _color_for_team, _rank_strip


def test_signal_colors():
    assert _color_for_team("Yankees", "Yankees") == "green"
    assert _color_for_team("Yankees", "Pirates") == "red"
    assert _color_for_team(None, "Pirates") == "gray"


def test_rank_strip_is_compact():
    category = {
        "season": {"rank": 2, "metric_name": "OPS", "metric_value": ".768"},
        "month": {"rank": 4, "metric_name": "OPS", "metric_value": ".800"},
        "week": {"rank": 8, "metric_name": "OPS", "metric_value": ".750"},
    }
    rendered = _rank_strip(category, "Batting")
    assert "S #2" in rendered
    assert "30 #4" in rendered
    assert "7 #8" in rendered
