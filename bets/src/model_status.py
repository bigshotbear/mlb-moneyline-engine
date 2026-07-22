from __future__ import annotations

MODEL_STATUS = {
    "stage": "EYE-TEST + INDICATOR TRACKER",
    "recommendations_enabled": False,
    "reason": (
        "The home screen now organizes matchup information and preliminary "
        "signal direction, but no direction is a calibrated betting recommendation."
    ),
}

SIGNAL_FAMILIES = [
    {"number": 1, "name": "Starting-pitcher projection", "purpose": "Starter skill, workload, sustainability, and supporting outcomes."},
    {"number": 2, "name": "Starter-versus-confirmed-lineup matchup", "purpose": "Handedness, arsenal, strikeout, walk, and contact fit."},
    {"number": 3, "name": "Confirmed-lineup strength and lineup shock", "purpose": "The actual nine and changes from expected personnel."},
    {"number": 4, "name": "High-leverage bullpen asymmetry", "purpose": "Talent, recent workload, and availability of likely relievers."},
    {"number": 5, "name": "Catching, baserunning, and hidden runs", "purpose": "Framing, blocking, throwing, baserunning, and stolen-base value."},
    {"number": 6, "name": "Batted-ball and defensive interaction", "purpose": "Likely contact type against position-specific defense."},
    {"number": 7, "name": "Situational and roster context", "purpose": "Asymmetric home, travel, rest, roster, workload, and park effects."},
]
