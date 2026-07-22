from src.mlb_data import _baseball_ip_to_outs, _outs_to_baseball_ip, _parse_lineup_side


def test_baseball_innings_conversion():
    assert _baseball_ip_to_outs("2.2") == 8
    assert _outs_to_baseball_ip(8) == "2.2"


def test_lineup_parser():
    side = {
        "team": {"id": 1, "name": "Test Team"},
        "battingOrder": [10, 20],
        "players": {
            "ID10": {"person": {"id": 10, "fullName": "Player One"}, "position": {"abbreviation": "CF"}},
            "ID20": {"person": {"id": 20, "fullName": "Player Two"}, "position": {"abbreviation": "SS"}},
        },
    }
    parsed = _parse_lineup_side(side)
    assert parsed["lineup"][0]["player"] == "Player One"
    assert parsed["confirmed"] is False
