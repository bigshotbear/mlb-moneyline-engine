from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import requests

from .config import SNAPSHOT_DIR, get_supabase_config


class SnapshotStoreError(RuntimeError):
    pass


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "snapshot"


def supabase_enabled() -> bool:
    url, key = get_supabase_config()
    return bool(url and key)


def save_snapshot(matchup_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _save_to_supabase(matchup_name, payload) if supabase_enabled() else _save_locally(matchup_name, payload)


def _save_to_supabase(matchup_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    url, key = get_supabase_config()
    assert url and key
    event = payload.get("event", {})
    schedule = payload.get("mlb_schedule_match") or {}
    lineups = payload.get("automated_data", {}).get("lineups", {})
    row = {
        "event_id": event.get("event_id"),
        "game_pk": schedule.get("game_pk"),
        "matchup": matchup_name,
        "commence_time": event.get("commence_time"),
        "lineups_confirmed": bool(lineups.get("away", {}).get("confirmed") and lineups.get("home", {}).get("confirmed")),
        "payload": payload,
    }
    response = requests.post(
        f"{url.rstrip('/')}/rest/v1/pregame_snapshots",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"},
        json=row,
        timeout=25,
    )
    if response.status_code not in (200, 201):
        raise SnapshotStoreError(f"Supabase save failed: HTTP {response.status_code}: {response.text[:500]}")
    returned = response.json()
    saved = returned[0] if isinstance(returned, list) and returned else row
    return {"source": "supabase", "identifier": saved.get("id"), "created_at": saved.get("created_at")}


def _save_locally(matchup_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    saved_payload = dict(payload)
    saved_payload["snapshot_created_at_utc"] = timestamp.isoformat()
    filename = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}_{_safe_slug(matchup_name)}.json"
    destination = SNAPSHOT_DIR / filename
    destination.write_text(json.dumps(saved_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return {"source": "local", "identifier": filename, "created_at": timestamp.isoformat()}


def list_snapshots(limit: int = 100) -> list[dict[str, Any]]:
    return _list_supabase(limit) if supabase_enabled() else _list_local(limit)


def _list_supabase(limit: int) -> list[dict[str, Any]]:
    url, key = get_supabase_config()
    assert url and key
    response = requests.get(
        f"{url.rstrip('/')}/rest/v1/pregame_snapshots",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        params={"select": "id,created_at,matchup,lineups_confirmed,payload", "order": "created_at.desc", "limit": limit},
        timeout=25,
    )
    if response.status_code != 200:
        raise SnapshotStoreError(f"Supabase read failed: HTTP {response.status_code}: {response.text[:500]}")
    return [
        {
            "source": "supabase",
            "identifier": row.get("id"),
            "created_at": row.get("created_at"),
            "matchup": row.get("matchup"),
            "lineups_confirmed": row.get("lineups_confirmed"),
            "payload": row.get("payload"),
        }
        for row in response.json()
    ]


def _list_local(limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(SNAPSHOT_DIR.glob("*.json"), reverse=True)[:limit]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        event = payload.get("event", {})
        lineups = payload.get("automated_data", {}).get("lineups", {})
        results.append({
            "source": "local",
            "identifier": path.name,
            "created_at": payload.get("snapshot_created_at_utc"),
            "matchup": f"{event.get('away_team')} at {event.get('home_team')}",
            "lineups_confirmed": bool(lineups.get("away", {}).get("confirmed") and lineups.get("home", {}).get("confirmed")),
            "payload": payload,
        })
    return results
