from src.live_game import base_state_text, live_watch_label
from src.slate_engine import adjusted_score


def test_coverage_adjustment():
    assert adjusted_score(85, 30.8) == 60.8
    assert adjusted_score(50, 30.8) == 50.0
    assert adjusted_score(85, 100) == 85.0


def test_base_state_text():
    state = {
        "runner_on_first": True,
        "runner_on_second": False,
        "runner_on_third": True,
    }
    assert base_state_text(state) == "1st, 3rd"


def test_better_price_watch():
    state = {
        "is_final": False,
        "is_live": True,
        "away_team": "A",
        "home_team": "B",
        "away_score": 1,
        "home_score": 2,
        "current_inning": 3,
        "inning_ordinal": "3rd",
        "inning_state": "Top",
    }
    result = live_watch_label(
        state=state,
        pregame_leader="A",
        adjusted_leader_score=60,
        coverage=40,
    )
    assert result["label"] == "BETTER-PRICE WATCH"
