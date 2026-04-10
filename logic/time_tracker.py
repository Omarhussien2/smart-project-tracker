"""
Smart time tracker module.
Calculates net work duration from timestamps log, handling multiple pause/resume cycles.
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(ts: str) -> Optional[datetime]:
    """Parse an ISO 8601 timestamp string into a datetime object."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def create_event(action: str) -> Dict[str, str]:
    """Create a timestamp event dict."""
    return {"action": action, "ts": now_utc_iso()}


def calculate_net_duration(timestamps_log: str) -> float:
    """
    Calculate net work duration in minutes from a timestamps_log JSON string.

    Handles multiple pause/resume cycles correctly:
    - Sums (pause - start) + (pause - resume) + ... for all completed intervals
    - If currently running (no matching pause/complete), adds (now - last start/resume)
    - Returns 0.0 if the log is empty or malformed

    Args:
        timestamps_log: JSON string of [{"action": "start|pause|resume|complete", "ts": "ISO"}, ...]

    Returns:
        Net duration in minutes (float, rounded to 2 decimal places)
    """
    if not timestamps_log:
        return 0.0

    try:
        events = json.loads(timestamps_log)
    except (json.JSONDecodeError, TypeError):
        return 0.0

    if not events:
        return 0.0

    total_seconds = 0.0
    interval_start = None

    for event in events:
        action = event.get("action", "")
        ts = parse_iso(event.get("ts", ""))

        if ts is None:
            continue

        if action in ("start", "resume"):
            interval_start = ts

        elif action in ("pause", "complete") and interval_start is not None:
            delta = (ts - interval_start).total_seconds()
            if delta > 0:
                total_seconds += delta
            interval_start = None  # interval closed

    # If currently running (interval_start set, no matching pause/complete)
    if interval_start is not None:
        now = datetime.now(timezone.utc)
        delta = (now - interval_start).total_seconds()
        if delta > 0:
            total_seconds += delta

    return round(total_seconds / 60.0, 2)


def format_duration(minutes: float) -> str:
    """
    Format minutes into a human-readable string.
    Example: 90.5 → "1h 30m", 45.0 → "45m", 0.5 → "30s"
    """
    if minutes <= 0:
        return "0m"

    total_seconds = int(minutes * 60)
    hours = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if mins > 0:
        parts.append(f"{mins}m")
    if not parts and secs > 0:
        parts.append(f"{secs}s")

    return " ".join(parts) if parts else "0m"


def get_status_from_log(timestamps_log: str) -> str:
    """
    Determine the current status from the last event in the log.
    Returns one of: idle, running, paused, completed
    """
    if not timestamps_log:
        return "idle"

    try:
        events = json.loads(timestamps_log)
    except (json.JSONDecodeError, TypeError):
        return "idle"

    if not events:
        return "idle"

    last_action = events[-1].get("action", "")
    status_map = {
        "start": "running",
        "pause": "paused",
        "resume": "running",
        "complete": "completed",
    }
    return status_map.get(last_action, "idle")
