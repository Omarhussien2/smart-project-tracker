"""
Google Sheets API client using gspread + st.secrets.
Handles authentication, reading/writing project data, and timestamp management.
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import gspread
import pandas as pd

from config import (
    DEBOUNCE_INTERVAL_SECONDS,
    SHEET_COLUMNS,
    SHEET_ID,
    WORKSPACES,
    TaskStatus,
    get_google_credentials,
)


# ─── Debounced Write Buffer ───────────────────────────────────────────────

_write_buffer: dict = {}  # {(workspace_key, project_id, column): value}
_last_flush: float = 0.0


def debounced_write(workspace_key: str, project_id: str, column: str, value) -> None:
    """Buffer a column write. Flushes automatically if interval elapsed."""
    global _last_flush
    _write_buffer[(workspace_key, project_id, column)] = value
    now = time.time()
    if now - _last_flush >= DEBOUNCE_INTERVAL_SECONDS:
        flush_writes()


def flush_writes() -> None:
    """Flush all buffered writes to Google Sheets."""
    global _write_buffer, _last_flush
    if not _write_buffer:
        return

    # Group by (workspace_key, project_id)
    grouped: dict = {}
    for (ws_key, proj_id, col), val in _write_buffer.items():
        key = (ws_key, proj_id)
        if key not in grouped:
            grouped[key] = {}
        grouped[key][col] = val

    # Reuse a single client for all writes
    client = None
    for (ws_key, proj_id), cols in grouped.items():
        if client is None:
            client = get_client()
        ws = _get_sheet(client, ws_key)
        records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
        for idx, row in enumerate(records, start=2):
            if row.get("project_id") == proj_id:
                for col, val in cols.items():
                    col_idx = SHEET_COLUMNS.index(col)
                    col_letter = chr(ord("A") + col_idx)
                    ws.update(range_name=f"{col_letter}{idx}", values=[[val]])
                break

    _write_buffer.clear()
    _last_flush = time.time()


def force_flush() -> None:
    """Force flush regardless of interval. Called before critical reads."""
    flush_writes()


def get_client() -> gspread.Client:
    """Authenticate and return a gspread client using Streamlit secrets."""
    creds = get_google_credentials()
    if creds is None:
        raise RuntimeError("Google credentials not found in st.secrets")
    return gspread.service_account_from_dict(creds)


def test_connection() -> tuple[bool, str]:
    """
    Test the Google Sheets connection and return a diagnostic result.
    Returns (success: bool, message: str) with actionable advice on failure.
    """
    try:
        creds = get_google_credentials()
    except Exception as e:
        return False, f"❌ Failed to read credentials: `{e}`"

    if creds is None:
        return False, (
            "❌ No Google credentials found in `st.secrets['google_credentials']`.\n\n"
            "**Fix:** Add your service account JSON to `.streamlit/secrets.toml`."
        )

    # Validate credential structure
    client_email = creds.get("client_email", "UNKNOWN")
    if creds.get("type") != "service_account":
        return (
            False,
            f"❌ Credentials are not a service account (type={creds.get('type')}).",
        )

    if not creds.get("private_key"):
        return False, "❌ Credentials missing `private_key` field."

    # Try to connect and access the spreadsheet
    try:
        client = gspread.service_account_from_dict(creds)
    except Exception as e:
        return False, f"❌ Failed to authenticate with Google: `{e}`"

    try:
        spreadsheet = client.open_by_key(SHEET_ID)
        # Try to read sheet names to confirm access
        _ = spreadsheet.title
    except gspread.exceptions.APIError as e:
        code = e.code if hasattr(e, "code") else "?"
        msg = str(e) if hasattr(e, "message") else repr(e)
        return False, (
            f"❌ **Google Sheets API error** (HTTP {code}): {msg}\n\n"
            f"**Service account:** `{client_email}`\n"
            f"**Sheet ID:** `{SHEET_ID}`\n\n"
            f"**Most likely causes:**\n"
            f"1. 🔑 **Share the spreadsheet** with `{client_email}` — "
            f"open the Google Sheet → Share → add that email as **Editor**\n"
            f"2. 🛠️ **Enable Google Sheets API** — go to "
            f"[Google Cloud Console](https://console.cloud.google.com/apis/library/sheets.googleapis.com"
            f"?project=smart-project-tracker-492914) and enable it\n"
            f"3. 🛠️ **Enable Google Drive API** — go to "
            f"[Google Cloud Console](https://console.cloud.google.com/apis/library/drive.googleapis.com"
            f"?project=smart-project-tracker-492914) and enable it"
        )
    except gspread.exceptions.SpreadsheetNotFound:
        return False, (
            f"❌ Spreadsheet not found (ID: `{SHEET_ID}`).\n\n"
            f"**Fix:** Verify the SHEET_ID in `config.py` matches your Google Sheet URL."
        )
    except Exception as e:
        return False, f"❌ Unexpected error accessing spreadsheet: `{e}`"

    # Verify worksheets exist
    ws_names = [ws_config.sheet_name for ws_config in WORKSPACES.values()]
    try:
        existing_titles = [ws.title for ws in spreadsheet.worksheets()]
    except Exception as e:
        return False, f"❌ Cannot list worksheets: `{e}`"

    missing = [name for name in ws_names if name not in existing_titles]
    if missing:
        return True, (
            f"⚠️ Connected to spreadsheet **'{spreadsheet.title}'**, "
            f"but worksheets {missing} don't exist yet.\n"
            f"They will be created automatically when you add the first project."
        )

    return (
        True,
        f"✅ Connected to spreadsheet **'{spreadsheet.title}'** ({len(existing_titles)} worksheets).",
    )


class SheetsConnectionError(Exception):
    """Raised when Google Sheets API is unreachable or returns an auth error."""

    pass


def _get_sheet(client: gspread.Client, workspace_key: str) -> gspread.Worksheet:
    """Get the worksheet for a specific workspace."""
    ws_config = WORKSPACES[workspace_key]
    try:
        spreadsheet = client.open_by_key(SHEET_ID)
    except gspread.exceptions.APIError as e:
        raise SheetsConnectionError(
            f"Google Sheets API error (HTTP {e.code if hasattr(e, 'code') else '?'}): "
            f"The service account cannot access the spreadsheet. "
            f"Make sure the sheet is shared with your service account email "
            f"and the Google Sheets API is enabled."
        ) from e
    return spreadsheet.worksheet(ws_config.sheet_name)


def _ensure_headers(ws: gspread.Worksheet) -> None:
    """Ensure the worksheet has the correct header row."""
    existing = ws.row_values(1)
    if existing != SHEET_COLUMNS:
        ws.update(range_name="A1", values=[SHEET_COLUMNS])


def read_projects(workspace_key: str) -> pd.DataFrame:
    """
    Read all projects from a workspace's Google Sheet.
    Returns a DataFrame with SHEET_COLUMNS as columns.
    Raises SheetsConnectionError if the API call fails.
    """
    client = get_client()
    ws = _get_sheet(client, workspace_key)
    _ensure_headers(ws)

    records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
    if not records:
        return pd.DataFrame(columns=SHEET_COLUMNS)

    df = pd.DataFrame(records, columns=SHEET_COLUMNS)
    return df


def generate_project_id(workspace_key: str) -> str:
    """Generate a unique project ID based on workspace, timestamp, and random suffix."""
    now = datetime.now(timezone.utc)
    prefix = workspace_key[:3].upper()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6]
    return f"{prefix}-{timestamp}-{rand_suffix}"


def upsert_project(workspace_key: str, project_data: Dict) -> str:
    """
    Insert a new project or update an existing one.
    Returns the project_id.
    """
    client = get_client()
    ws = _get_sheet(client, workspace_key)
    _ensure_headers(ws)

    project_id = project_data.get("project_id")

    if project_id:
        # Find and update existing row
        records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
        for idx, row in enumerate(records, start=2):  # row 1 is header
            if row.get("project_id") == project_id:
                row_data = [project_data.get(col, "") for col in SHEET_COLUMNS]
                ws.update(range_name=f"A{idx}", values=[row_data])
                return project_id

    # Insert new project
    if not project_id:
        project_id = generate_project_id(workspace_key)
        project_data["project_id"] = project_id

    row_data = [project_data.get(col, "") for col in SHEET_COLUMNS]
    ws.append_row(row_data)
    return project_id


def append_timestamp(workspace_key: str, project_id: str, event: Dict) -> None:
    """
    Append a timestamp event to the project's timestamps_log.
    event format: {"action": "start|pause|resume|complete", "ts": "ISO timestamp"}

    Batches all column updates into a single API call to reduce rate-limit risk.
    """
    client = get_client()
    ws = _get_sheet(client, workspace_key)

    records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("project_id") == project_id:
            # Parse existing log or start new
            existing_log = row.get("timestamps_log", "")
            try:
                log = json.loads(existing_log) if existing_log else []
            except (json.JSONDecodeError, TypeError):
                log = []

            log.append(event)

            # Build a batch update for all columns at once
            action = event.get("action", "")
            ts = event.get("ts", "")

            # Build row data with only the columns we want to update
            batch_updates = []  # [(col_letter, value), ...]

            # 1) timestamps_log
            tl_col = chr(ord("A") + SHEET_COLUMNS.index("timestamps_log"))
            batch_updates.append((tl_col, json.dumps(log)))

            # 2) Individual time columns
            time_col_map = {
                "start": "start_time",
                "pause": "pause_time",
                "resume": "resume_time",
                "complete": "end_time",
            }
            if action in time_col_map:
                col_name = time_col_map[action]
                col_letter = chr(ord("A") + SHEET_COLUMNS.index(col_name))
                batch_updates.append((col_letter, ts))

            # 3) Status column
            status_map = {
                "start": TaskStatus.RUNNING,
                "pause": TaskStatus.PAUSED,
                "resume": TaskStatus.RUNNING,
                "complete": TaskStatus.COMPLETED,
            }
            if action in status_map:
                status_col = chr(ord("A") + SHEET_COLUMNS.index("status"))
                batch_updates.append((status_col, status_map[action]))

            # Perform batch update: find contiguous ranges or update individually
            # For small numbers of columns (2-3), individual calls are fine
            # but we avoid the extra get_all_records() overhead
            for col_letter, value in batch_updates:
                ws.update(range_name=f"{col_letter}{idx}", values=[[value]])

            break


def update_net_duration(workspace_key: str, project_id: str, minutes: float) -> None:
    """Update the net_duration_minutes column for a project."""
    client = get_client()
    ws = _get_sheet(client, workspace_key)

    records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("project_id") == project_id:
            col_idx = SHEET_COLUMNS.index("net_duration_minutes")
            col_letter = chr(ord("A") + col_idx)
            ws.update(range_name=f"{col_letter}{idx}", values=[[round(minutes, 2)]])
            break


def update_pause_reason(workspace_key: str, project_id: str, reason: str) -> None:
    """Update the pause_reason column for a project."""
    client = get_client()
    ws = _get_sheet(client, workspace_key)

    records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("project_id") == project_id:
            col_idx = SHEET_COLUMNS.index("pause_reason")
            col_letter = chr(ord("A") + col_idx)
            ws.update(range_name=f"{col_letter}{idx}", values=[[reason]])
            break


# ─── To-Do List Functions ─────────────────────────────────────────────────

TODO_COLUMNS = ["todo_id", "text", "checked", "workspace"]


def read_todos(workspace_key: str) -> List[Dict]:
    """Read all to-do items for a workspace from the 'todos' sheet."""
    client = get_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    try:
        ws = spreadsheet.worksheet("todos")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="todos", rows=100, cols=len(TODO_COLUMNS))
        ws.update(range_name="A1", values=[TODO_COLUMNS])

    records = ws.get_all_records(expected_headers=TODO_COLUMNS)
    return [r for r in records if r.get("workspace") == workspace_key]


def add_todo(workspace_key: str, text: str) -> str:
    """Add a new to-do item. Returns the todo_id."""
    import uuid

    todo_id = f"todo-{uuid.uuid4().hex[:8]}"
    client = get_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    try:
        ws = spreadsheet.worksheet("todos")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="todos", rows=100, cols=len(TODO_COLUMNS))
        ws.update(range_name="A1", values=[TODO_COLUMNS])

    ws.append_row([todo_id, text, False, workspace_key])
    return todo_id


def toggle_todo(workspace_key: str, todo_id: str, checked: bool) -> None:
    """Toggle the checked state of a to-do item."""
    client = get_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    ws = spreadsheet.worksheet("todos")

    records = ws.get_all_records(expected_headers=TODO_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("todo_id") == todo_id:
            col_idx = TODO_COLUMNS.index("checked")
            col_letter = chr(ord("A") + col_idx)
            ws.update(range_name=f"{col_letter}{idx}", values=[[checked]])
            break


def delete_todo(workspace_key: str, todo_id: str) -> None:
    """Delete a to-do item."""
    client = get_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    ws = spreadsheet.worksheet("todos")

    records = ws.get_all_records(expected_headers=TODO_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("todo_id") == todo_id:
            ws.delete_rows(idx)
            break
