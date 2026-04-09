"""
Session state management helpers for Streamlit.
Manages card button states, form visibility, and workspace-level state.
"""

from typing import Dict, Optional

import streamlit as st

from config import TaskStatus


def init_project_state(project_id: str, current_status: str = TaskStatus.IDLE) -> None:
    """
    Initialize session state for a project card if not already present.
    Stores the card's current status and transient form data.
    """
    key = f"proj_{project_id}"
    if key not in st.session_state:
        st.session_state[key] = {
            "status": current_status,
            "pause_reason": "",
        }


def get_project_status(project_id: str) -> str:
    """Get the current status of a project from session state."""
    key = f"proj_{project_id}"
    if key in st.session_state:
        return st.session_state[key].get("status", TaskStatus.IDLE)
    return TaskStatus.IDLE


def set_project_status(project_id: str, status: str) -> None:
    """Update the status of a project in session state."""
    key = f"proj_{project_id}"
    if key not in st.session_state:
        st.session_state[key] = {"status": status, "pause_reason": ""}
    else:
        st.session_state[key]["status"] = status


def get_pause_reason(project_id: str) -> str:
    """Get the pause reason for a project."""
    key = f"proj_{project_id}"
    if key in st.session_state:
        return st.session_state[key].get("pause_reason", "")
    return ""


def set_pause_reason(project_id: str, reason: str) -> None:
    """Set the pause reason for a project."""
    key = f"proj_{project_id}"
    if key not in st.session_state:
        st.session_state[key] = {"status": TaskStatus.IDLE, "pause_reason": reason}
    else:
        st.session_state[key]["pause_reason"] = reason


def init_form_state(workspace_key: str) -> None:
    """Initialize the 'Add New Project' form state."""
    key = f"form_open_{workspace_key}"
    if key not in st.session_state:
        st.session_state[key] = False


def is_form_open(workspace_key: str) -> bool:
    """Check if the 'Add New Project' form is open."""
    return st.session_state.get(f"form_open_{workspace_key}", False)


def toggle_form(workspace_key: str) -> None:
    """Toggle the 'Add New Project' form visibility."""
    key = f"form_open_{workspace_key}"
    st.session_state[key] = not st.session_state.get(key, False)


def init_todo_form(workspace_key: str) -> None:
    """Initialize the 'Add To-Do' input state."""
    key = f"todo_input_{workspace_key}"
    if key not in st.session_state:
        st.session_state[key] = ""


def clear_project_state(project_id: str) -> None:
    """Remove all session state for a project (used after page reset)."""
    key = f"proj_{project_id}"
    if key in st.session_state:
        del st.session_state[key]


def rebuild_session_from_sheets(projects_df) -> None:
    """
    Rebuild session state from Google Sheets data.
    Called on every page load to ensure state matches the persisted source of truth.

    Args:
        projects_df: DataFrame with SHEET_COLUMNS as columns
    """
    from logic.time_tracker import get_status_from_log

    if projects_df.empty:
        return

    for _, row in projects_df.iterrows():
        project_id = row.get("project_id", "")
        if not project_id:
            continue

        # Determine status from timestamps_log (source of truth)
        timestamps_log = row.get("timestamps_log", "")
        sheet_status = get_status_from_log(
            timestamps_log if isinstance(timestamps_log, str) else ""
        )

        # Initialize and set correct status
        init_project_state(project_id, sheet_status)

        key = f"proj_{project_id}"
        st.session_state[key]["status"] = sheet_status

        # Restore pause reason from Sheets
        pause_reason = row.get("pause_reason", "")
        if pause_reason and isinstance(pause_reason, str):
            st.session_state[key]["pause_reason"] = pause_reason
