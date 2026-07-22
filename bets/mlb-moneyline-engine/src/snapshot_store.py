from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "snapshot"


def save_snapshot(
    snapshot_dir: Path,
    matchup_name: str,
    payload: dict[str, Any],
) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    saved_payload = dict(payload)
    saved_payload["snapshot_created_at_utc"] = timestamp.isoformat()

    filename = (
        f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}_"
        f"{_safe_slug(matchup_name)}.json"
    )
    destination = snapshot_dir / filename
    destination.write_text(
        json.dumps(saved_payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return destination


def list_snapshots(snapshot_dir: Path) -> list[Path]:
    if not snapshot_dir.exists():
        return []
    return sorted(snapshot_dir.glob("*.json"), reverse=True)


def read_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
