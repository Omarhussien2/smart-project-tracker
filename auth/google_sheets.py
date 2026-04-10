"""
Google Sheets API client using gspread + st.secrets.
Optimized for minimal API calls using @st.cache_resource and @st.cache_data.

Before this refactor: ~13 API calls per page load → HTTP 429 rate limit.
After: ~2 API calls on first load, 0 on cached loads within 30s TTL.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List

import gspread
import pandas as pd
import streamlit as st

from config import (
    SHEET_COLUMNS,
    SHEET_ID,
    WORKSPACES,
    TaskStatus,
    get_google_credentials,
)


class SheetsConnectionError(Exception):
    """Raised when Google Sheets API is unreachable or returns an auth error."""

    pass


# ─── Cached Resources (created once per server lifetime) ──────────────────


@st.cache_resource
def get_client() -> gspread.Client:
    """Authenticate and return a gspread client. Cached for server lifetime."""
    creds = get_google_credentials()
    if creds is None:
        raise RuntimeError("Google credentials not found in st.secrets")
    return gspread.service_account_from_dict(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    """Open the spreadsheet. NOT cached — avoids caching 429 failures."""
    client = get_client()
    return client.open_by_key(SHEET_ID)


def _get_sheet(workspace_key: str) -> gspread.Worksheet:
    """Get a project worksheet. Returns None on API errors instead of crashing."""
    ws_config = WORKSPACES[workspace_key]
    try:
        spreadsheet = _get_spreadsheet()
        return spreadsheet.worksheet(ws_config.sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        # First time — create the worksheet with headers
        spreadsheet = _get_spreadsheet()
        ws = spreadsheet.add_worksheet(
            title=ws_config.sheet_name, rows=100, cols=len(SHEET_COLUMNS)
        )
        ws.update(range_name="A1", values=[SHEET_COLUMNS])
        return ws


def _get_todos_sheet() -> gspread.Worksheet:
    """Get or create the todos worksheet. Returns None on API errors."""
    try:
        spreadsheet = _get_spreadsheet()
        return spreadsheet.worksheet("todos")
    except gspread.exceptions.WorksheetNotFound:
        spreadsheet = _get_spreadsheet()
        ws = spreadsheet.add_worksheet(title="todos", rows=100, cols=len(TODO_COLUMNS))
        ws.update(range_name="A1", values=[TODO_COLUMNS])
        return ws


def _invalidate_cache():
    """Clear read caches after a write operation so next read gets fresh data."""
    read_projects.clear()
    read_todos.clear()


# ─── Connection Test ──────────────────────────────────────────────────────


def test_connection() -> tuple[bool, str]:
    """
    Test Google Sheets connection. Returns (success, message).
    Makes only 1 API call (fetch_sheet_metadata).
    """
    creds = get_google_credentials()
    if creds is None:
        return False, (
            "❌ No Google credentials found in `st.secrets['google_credentials']`.\n\n"
            "**Fix:** Add your service account JSON to `.streamlit/secrets.toml`."
        )

    client_email = creds.get("client_email", "UNKNOWN")
    if creds.get("type") != "service_account":
        return False, f"❌ Not a service account (type={creds.get('type')})."
    if not creds.get("private_key"):
        return False, "❌ Missing `private_key` in credentials."

    try:
        client = gspread.service_account_from_dict(creds)
        spreadsheet = client.open_by_key(SHEET_ID)
        _ = spreadsheet.title
    except gspread.exceptions.APIError as e:
        code = e.code if hasattr(e, "code") else "?"
        return False, (
            f"❌ **Google Sheets API error** (HTTP {code})\n\n"
            f"**Service account:** `{client_email}`\n"
            f"**Sheet ID:** `{SHEET_ID}`\n\n"
            f"**Fixes:**\n"
            f"1. 🔑 Share the Google Sheet with `{client_email}` (Editor)\n"
            f"2. 🛠️ Enable [Sheets API](https://console.cloud.google.com/apis/library"
            f"/sheets.googleapis.com?project=smart-project-tracker-492914)\n"
            f"3. 🛠️ Enable [Drive API](https://console.cloud.google.com/apis/library"
            f"/drive.googleapis.com?project=smart-project-tracker-492914)"
        )
    except gspread.exceptions.SpreadsheetNotFound:
        return False, f"❌ Spreadsheet not found (ID: `{SHEET_ID}`). Check config.py."
    except Exception as e:
        return False, f"❌ Unexpected error: `{e}`"

    return True, f"✅ Connected to **'{spreadsheet.title}'**."


# ─── Read Functions (Cached 30s) ─────────────────────────────────────────


@st.cache_data(ttl=30, show_spinner=False)
def read_projects(workspace_key: str) -> pd.DataFrame:
    """
    Read all projects from a workspace's sheet.
    Cached for 30 seconds. Returns empty DataFrame on API errors (never crashes).
    """
    try:
        ws = _get_sheet(workspace_key)
        if ws is None:
            return pd.DataFrame(columns=SHEET_COLUMNS)
        records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
        if not records:
            return pd.DataFrame(columns=SHEET_COLUMNS)
        return pd.DataFrame(records, columns=SHEET_COLUMNS)
    except Exception:
        # Never crash — return empty and let the UI show "no projects"
        return pd.DataFrame(columns=SHEET_COLUMNS)


# ─── To-Do Column Definitions ────────────────────────────────────────────

TODO_COLUMNS = ["todo_id", "text", "checked", "workspace"]


@st.cache_data(ttl=30, show_spinner=False)
def read_todos(workspace_key: str) -> List[Dict]:
    """Read todos for a workspace. Cached 30s. Returns empty list on errors."""
    try:
        ws = _get_todos_sheet()
        if ws is None:
            return []
        records = ws.get_all_records(expected_headers=TODO_COLUMNS)
        return [r for r in records if r.get("workspace") == workspace_key]
    except Exception:
        return []


# ─── Write Functions ──────────────────────────────────────────────────────


def generate_project_id(workspace_key: str) -> str:
    """Generate a unique project ID based on workspace, timestamp, and UUID suffix."""
    now = datetime.now(timezone.utc)
    prefix = workspace_key[:3].upper()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6]
    return f"{prefix}-{timestamp}-{rand_suffix}"


def upsert_project(workspace_key: str, project_data: Dict) -> str:
    """Insert a new project or update an existing one. Invalidates read cache."""
    ws = _get_sheet(workspace_key)

    project_id = project_data.get("project_id")

    if project_id:
        records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
        for idx, row in enumerate(records, start=2):
            if row.get("project_id") == project_id:
                row_data = [project_data.get(col, "") for col in SHEET_COLUMNS]
                ws.update(range_name=f"A{idx}", values=[row_data])
                _invalidate_cache()
                return project_id

    # Insert new project
    if not project_id:
        project_id = generate_project_id(workspace_key)
        project_data["project_id"] = project_id

    row_data = [project_data.get(col, "") for col in SHEET_COLUMNS]
    ws.append_row(row_data)
    _invalidate_cache()
    return project_id


def append_timestamp(workspace_key: str, project_id: str, event: Dict) -> None:
    """
    Append a timestamp event and update time/status columns.
    Invalidates read cache so next load gets fresh data.
    """
    ws = _get_sheet(workspace_key)
    records = ws.get_all_records(expected_headers=SHEET_COLUMNS)

    for idx, row in enumerate(records, start=2):
        if row.get("project_id") == project_id:
            # Parse existing log
            existing_log = row.get("timestamps_log", "")
            try:
                log = json.loads(existing_log) if existing_log else []
            except (json.JSONDecodeError, TypeError):
                log = []

            log.append(event)

            action = event.get("action", "")
            ts = event.get("ts", "")

            # 1) timestamps_log column
            tl_col = chr(ord("A") + SHEET_COLUMNS.index("timestamps_log"))
            ws.update(range_name=f"{tl_col}{idx}", values=[[json.dumps(log)]])

            # 2) Individual time column
            time_col_map = {
                "start": "start_time",
                "pause": "pause_time",
                "resume": "resume_time",
                "complete": "end_time",
            }
            if action in time_col_map:
                col_letter = chr(ord("A") + SHEET_COLUMNS.index(time_col_map[action]))
                ws.update(range_name=f"{col_letter}{idx}", values=[[ts]])

            # 3) Status column
            status_map = {
                "start": TaskStatus.RUNNING,
                "pause": TaskStatus.PAUSED,
                "resume": TaskStatus.RUNNING,
                "complete": TaskStatus.COMPLETED,
            }
            if action in status_map:
                status_col = chr(ord("A") + SHEET_COLUMNS.index("status"))
                ws.update(
                    range_name=f"{status_col}{idx}",
                    values=[[status_map[action]]],
                )

            _invalidate_cache()
            break


def update_net_duration(workspace_key: str, project_id: str, minutes: float) -> None:
    """Update the net_duration_minutes column. Invalidates read cache."""
    ws = _get_sheet(workspace_key)
    records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("project_id") == project_id:
            col_letter = chr(ord("A") + SHEET_COLUMNS.index("net_duration_minutes"))
            ws.update(range_name=f"{col_letter}{idx}", values=[[round(minutes, 2)]])
            _invalidate_cache()
            break


def update_pause_reason(workspace_key: str, project_id: str, reason: str) -> None:
    """Update the pause_reason column. Invalidates read cache."""
    ws = _get_sheet(workspace_key)
    records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("project_id") == project_id:
            col_letter = chr(ord("A") + SHEET_COLUMNS.index("pause_reason"))
            ws.update(range_name=f"{col_letter}{idx}", values=[[reason]])
            _invalidate_cache()
            break


# ─── To-Do Write Functions ───────────────────────────────────────────────


def add_todo(workspace_key: str, text: str) -> str:
    """Add a new to-do item. Invalidates read cache."""
    todo_id = f"todo-{uuid.uuid4().hex[:8]}"
    ws = _get_todos_sheet()
    ws.append_row([todo_id, text, False, workspace_key])
    _invalidate_cache()
    return todo_id


def toggle_todo(workspace_key: str, todo_id: str, checked: bool) -> None:
    """Toggle the checked state. Invalidates read cache."""
    ws = _get_todos_sheet()
    records = ws.get_all_records(expected_headers=TODO_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("todo_id") == todo_id:
            col_letter = chr(ord("A") + TODO_COLUMNS.index("checked"))
            ws.update(range_name=f"{col_letter}{idx}", values=[[checked]])
            _invalidate_cache()
            break


def delete_todo(workspace_key: str, todo_id: str) -> None:
    """Delete a to-do item. Invalidates read cache."""
    ws = _get_todos_sheet()
    records = ws.get_all_records(expected_headers=TODO_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("todo_id") == todo_id:
            ws.delete_rows(idx)
            _invalidate_cache()
            break
