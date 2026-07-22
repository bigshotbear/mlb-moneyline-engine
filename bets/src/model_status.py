from __future__ import annotations

MODEL_STATUS = {
    "stage": "BEST BETS + LIVE CENTER",
    "recommendations_enabled": False,
    "reason": (
        "The app ranks the full slate using coverage-adjusted matchup scores and "
        "adds a separate live-game screen. Labels remain provisional until validated."
    ),
}

SIGNAL_FAMILIES = [
    {"number": 1, "name": "Starting pitcher", "purpose": "Eight raw starter checks with a 25-point family cap."},
    {"number": 2, "name": "Offense and confirmed lineup", "purpose": "Nine raw lineup/offense checks with a 25-point family cap."},
    {"number": 3, "name": "Bullpen", "purpose": "Six raw bullpen checks with a 20-point family cap."},
    {"number": 4, "name": "Defense and hidden runs", "purpose": "Four raw checks with a 10-point family cap."},
    {"number": 5, "name": "Context", "purpose": "Two raw context checks with a 10-point family cap."},
    {"number": 6, "name": "Market value", "purpose": "One price-edge check with a 10-point family cap."},
]
