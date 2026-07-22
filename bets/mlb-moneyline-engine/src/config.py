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


def ensure_directories() -> None:
    for path in (DATA_DIR, SNAPSHOT_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _read_secret(name: str) -> Optional[str]:
    env_value = os.getenv(name)
    if env_value:
        return env_value.strip()
    if st is not None:
        try:
            value = st.secrets.get(name)
            if value:
                return str(value).strip()
        except Exception:
            pass
    return None


def get_odds_api_key() -> Optional[str]:
    return _read_secret("ODDS_API_KEY")


def get_supabase_config() -> tuple[Optional[str], Optional[str]]:
    return _read_secret("SUPABASE_URL"), _read_secret("SUPABASE_SERVICE_ROLE_KEY")
