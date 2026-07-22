from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def format_game_time_et(value: str | None) -> str:
    if not value:
        return "Time TBD"

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "Time TBD"

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    local = parsed.astimezone(EASTERN)
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{local.strftime('%a, %b')} {local.day} • {hour}:{local.strftime('%M %p')} ET"


def format_moneyline(value: int | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+d}"


def rank_text(entry: dict[str, Any]) -> str:
    rank = entry.get("rank")
    metric_name = entry.get("metric_name")
    metric_value = entry.get("metric_value")

    if rank is None:
        return "N/A"

    metric = ""
    if metric_name and metric_value and metric_value != "N/A":
        metric = f" • {metric_name} {metric_value}"

    return f"#{rank}{metric}"
