from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import streamlit as st
except Exception:
    st = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
CACHE_DIR = DATA_DIR / "cache"
MANUAL_DIR = DATA_DIR / "manual"


def ensure_directories() -> None:
    for path in (DATA_DIR, SNAPSHOT_DIR, CACHE_DIR, MANUAL_DIR):
        path.mkdir(parents=True, exist_ok=True)


def get_odds_api_key() -> Optional[str]:
    env_value = os.getenv("ODDS_API_KEY")
    if env_value:
        return env_value.strip()

    if st is not None:
        try:
            value = st.secrets.get("ODDS_API_KEY")
            if value:
                return str(value).strip()
        except Exception:
            pass

    return None
