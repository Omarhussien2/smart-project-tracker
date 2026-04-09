"""
Google Sheets API client using gspread + st.secrets.
Handles authentication, reading/writing project data, and timestamp management.
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

import gspread
import pandas as pd

from config import (
    SHEET_COLUMNS,
    SHEET_NAME,
    WORKSPACES,
    TaskStatus,
    get_google_credentials,
)


def get_client() -> gspread.Client:
    """Authenticate and return a gspread client using Streamlit secrets."""
    creds = get_google_credentials()
    if creds is None:
        raise RuntimeError("Google credentials not found in st.secrets")
    return gspread.service_account_from_dict(creds)


def _get_sheet(client: gspread.Client, workspace_key: str) -> gspread.Worksheet:
    """Get the worksheet for a specific workspace."""
    ws_config = WORKSPACES[workspace_key]
    spreadsheet = client.open(SHEET_NAME)
    return spreadsheet.worksheet(ws_config.sheet_name)


def _ensure_headers(ws: gspread.Worksheet) -> None:
    """Ensure the worksheet has the correct header row."""
    existing = ws.row_values(1)
    if existing != SHEET_COLUMNS:
        ws.update("A1", [SHEET_COLUMNS])


def read_projects(workspace_key: str) -> pd.DataFrame:
    """
    Read all projects from a workspace's Google Sheet.
    Returns a DataFrame with SHEET_COLUMNS as columns.
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
    """Generate a unique project ID based on workspace and timestamp."""
    now = datetime.now(timezone.utc)
    prefix = workspace_key[:3].upper()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}"


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
                ws.update(f"A{idx}", [row_data])
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

            # Update timestamps_log column (column index 12 = L)
            col_letter = chr(ord("A") + SHEET_COLUMNS.index("timestamps_log"))
            ws.update(f"{col_letter}{idx}", [json.dumps(log)])

            # Also update the individual time columns
            action = event.get("action", "")
            ts = event.get("ts", "")

            time_col_map = {
                "start": "start_time",
                "pause": "pause_time",
                "resume": "resume_time",
                "complete": "end_time",
            }
            if action in time_col_map:
                col_name = time_col_map[action]
                col_idx = SHEET_COLUMNS.index(col_name)
                col_letter = chr(ord("A") + col_idx)
                ws.update(f"{col_letter}{idx}", [ts])

            # Update status column
            status_map = {
                "start": TaskStatus.RUNNING,
                "pause": TaskStatus.PAUSED,
                "resume": TaskStatus.RUNNING,
                "complete": TaskStatus.COMPLETED,
            }
            if action in status_map:
                status_col_idx = SHEET_COLUMNS.index("status")
                status_col_letter = chr(ord("A") + status_col_idx)
                ws.update(f"{status_col_letter}{idx}", [status_map[action]])

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
            ws.update(f"{col_letter}{idx}", [round(minutes, 2)])
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
            ws.update(f"{col_letter}{idx}", [reason])
            break


# ─── To-Do List Functions ─────────────────────────────────────────────────

TODO_COLUMNS = ["todo_id", "text", "checked", "workspace"]


def read_todos(workspace_key: str) -> List[Dict]:
    """Read all to-do items for a workspace from the 'todos' sheet."""
    client = get_client()
    spreadsheet = client.open(SHEET_NAME)

    try:
        ws = spreadsheet.worksheet("todos")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title="todos", rows=100, cols=len(TODO_COLUMNS)
        )
        ws.update("A1", [TODO_COLUMNS])

    records = ws.get_all_records(expected_headers=TODO_COLUMNS)
    return [r for r in records if r.get("workspace") == workspace_key]


def add_todo(workspace_key: str, text: str) -> str:
    """Add a new to-do item. Returns the todo_id."""
    import uuid

    todo_id = f"todo-{uuid.uuid4().hex[:8]}"
    client = get_client()
    spreadsheet = client.open(SHEET_NAME)

    try:
        ws = spreadsheet.worksheet("todos")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title="todos", rows=100, cols=len(TODO_COLUMNS)
        )
        ws.update("A1", [TODO_COLUMNS])

    ws.append_row([todo_id, text, False, workspace_key])
    return todo_id


def toggle_todo(workspace_key: str, todo_id: str, checked: bool) -> None:
    """Toggle the checked state of a to-do item."""
    client = get_client()
    spreadsheet = client.open(SHEET_NAME)
    ws = spreadsheet.worksheet("todos")

    records = ws.get_all_records(expected_headers=TODO_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("todo_id") == todo_id:
            col_idx = TODO_COLUMNS.index("checked")
            col_letter = chr(ord("A") + col_idx)
            ws.update(f"{col_letter}{idx}", [checked])
            break


def delete_todo(workspace_key: str, todo_id: str) -> None:
    """Delete a to-do item."""
    client = get_client()
    spreadsheet = client.open(SHEET_NAME)
    ws = spreadsheet.worksheet("todos")

    records = ws.get_all_records(expected_headers=TODO_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("todo_id") == todo_id:
            ws.delete_rows(idx)
            break
