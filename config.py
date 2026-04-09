"""
Configuration and constants for Smart Project Tracker Dashboard.
Defines workspace settings, categories, statuses, and sheet column mappings.
"""

import streamlit as st
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class WorkspaceConfig:
    """Immutable configuration for a single workspace."""
    name: str
    sheet_name: str
    icon: str
    primary_color: str
    secondary_color: str
    accent_color: str
    categories: List[str]


# ─── Workspace Definitions ────────────────────────────────────────────────

WORKSPACES: Dict[str, WorkspaceConfig] = {
    "samawah": WorkspaceConfig(
        name="Samawah",
        sheet_name="samawah_projects",
        icon="🏢",
        primary_color="#1a73e8",
        secondary_color="#e8f0fe",
        accent_color="#4285f4",
        categories=[
            "Development",
            "Design",
            "Meeting",
            "Research",
            "Documentation",
            "Testing",
            "DevOps",
            "Planning",
            "Bug Fix",
            "Other",
        ],
    ),
    "kinder": WorkspaceConfig(
        name="Kinder Market",
        sheet_name="kinder_projects",
        icon="🛒",
        primary_color="#e8710a",
        secondary_color="#fef3e2",
        accent_color="#f59e0b",
        categories=[
            "Marketing",
            "Inventory",
            "Sales",
            "Supplier",
            "Delivery",
            "Customer Service",
            "Finance",
            "Social Media",
            "Product",
            "Other",
        ],
    ),
}

# ─── Status Definitions ───────────────────────────────────────────────────

class TaskStatus:
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"

    @classmethod
    def all_statuses(cls) -> List[str]:
        return [cls.IDLE, cls.RUNNING, cls.PAUSED, cls.COMPLETED]

    @classmethod
    def button_visibility(cls, status: str) -> Dict[str, bool]:
        """Returns which action buttons should be visible for a given status."""
        return {
            TaskStatus.IDLE:       {"start": True,  "pause": False, "resume": False, "complete": False},
            TaskStatus.RUNNING:    {"start": False, "pause": True,  "resume": False, "complete": True},
            TaskStatus.PAUSED:     {"start": False, "pause": False, "resume": True,  "complete": True},
            TaskStatus.COMPLETED:  {"start": False, "pause": False, "resume": False, "complete": False},
        }.get(status, {"start": True, "pause": False, "resume": False, "complete": False})


# ─── Google Sheets Column Mapping ─────────────────────────────────────────

SHEET_COLUMNS = [
    "project_id",
    "task_description",
    "category",
    "status",
    "start_time",
    "pause_time",
    "resume_time",
    "end_time",
    "pause_reason",
    "net_duration_minutes",
    "doc_link",
    "timestamps_log",
]

# ─── App Settings ─────────────────────────────────────────────────────────

APP_TITLE = "Smart Project Tracker"
APP_ICON = "📊"
SHEET_NAME = "Smart Project Tracker"  # Name of the Google Spreadsheet
CACHE_TTL_SECONDS = 30  # Refresh data every 30 seconds

# ─── Credentials ──────────────────────────────────────────────────────────


def get_google_credentials() -> Optional[Dict]:
    """
    Retrieve Google service account credentials from Streamlit secrets.
    Returns a dict of credential key/value pairs, or None if unavailable/invalid.
    """
    try:
        creds = dict(st.secrets["google_credentials"])
        if creds.get("type") != "service_account":
            return None
        if not creds.get("private_key"):
            return None
        return creds
    except Exception:
        return None


def has_google_credentials() -> bool:
    """Check whether Google credentials are available in Streamlit secrets."""
    return get_google_credentials() is not None
