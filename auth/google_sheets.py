"""
Google Sheets API client — BULLETPROOF edition.
Zero decorators. Manual session_state caching. Never crashes the page.

API call budget per page load:
  - First load or cache expired: 2 calls (1 per workspace: open_by_key + get_all_records)
  - Cached (within 60s TTL): 0 calls
  - After a write: cache invalidated, next load = 2 calls
"""

import json
import time
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

TODO_COLUMNS = ["todo_id", "text", "checked", "workspace"]

CACHE_TTL = 60  # seconds — how long read data stays fresh


# ─── Helpers ──────────────────────────────────────────────────────────────


def _ts() -> float:
    return time.time()


def _is_fresh(key: str, ttl: float = CACHE_TTL) -> bool:
    """Check if a session_state cache key is still within TTL."""
    ts_key = f"{key}_ts"
    return key in st.session_state and (_ts() - st.session_state.get(ts_key, 0)) < ttl


def _store(key: str, value):
    """Store a value + its timestamp in session_state."""
    st.session_state[key] = value
    st.session_state[f"{key}_ts"] = _ts()


def _clear_cache():
    """Invalidate all read caches."""
    for ws in WORKSPACES:
        for k in [f"_proj_{ws}", f"_todos_{ws}"]:
            st.session_state.pop(k, None)
            st.session_state.pop(f"{k}_ts", None)


# ─── Client / Spreadsheet (lightweight, no decorator) ────────────────────


def _get_client() -> gspread.Client:
    """Create a gspread client. Not cached — gspread handles token reuse."""
    creds = get_google_credentials()
    if creds is None:
        raise ConnectionError("No Google credentials found")
    return gspread.service_account_from_dict(creds)


def _open_spreadsheet() -> gspread.Spreadsheet:
    """Open the spreadsheet by ID. Makes 1 metadata API call."""
    return _get_client().open_by_key(SHEET_ID)


def _get_sheet(workspace_key: str) -> gspread.Worksheet:
    """Get a worksheet for a workspace. Creates it if missing."""
    ss = _open_spreadsheet()
    ws_name = WORKSPACES[workspace_key].sheet_name
    try:
        return ss.worksheet(ws_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=ws_name, rows=100, cols=len(SHEET_COLUMNS))
        ws.update(range_name="A1", values=[SHEET_COLUMNS])
        return ws


def _get_todos_sheet() -> gspread.Worksheet:
    """Get or create the todos worksheet."""
    ss = _open_spreadsheet()
    try:
        return ss.worksheet("todos")
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title="todos", rows=100, cols=len(TODO_COLUMNS))
        ws.update(range_name="A1", values=[TODO_COLUMNS])
        return ws


# ─── Read Functions (session_state cached, never crash) ──────────────────


def read_projects(workspace_key: str) -> pd.DataFrame:
    """
    Read projects from Google Sheets.
    Returns cached data if fresh, otherwise fetches from API.
    NEVER crashes — returns empty DataFrame on any error.
    """
    cache_key = f"_proj_{workspace_key}"

    # Return cached data if still fresh
    if _is_fresh(cache_key):
        return st.session_state[cache_key]

    # Fetch from API
    try:
        ws = _get_sheet(workspace_key)
        records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
        df = (
            pd.DataFrame(records, columns=SHEET_COLUMNS)
            if records
            else pd.DataFrame(columns=SHEET_COLUMNS)
        )
        _store(cache_key, df)
        return df
    except Exception:
        # Don't cache failures — return empty but retry on next load
        return pd.DataFrame(columns=SHEET_COLUMNS)


def read_todos(workspace_key: str) -> List[Dict]:
    """Read todos. Session_state cached. Returns [] on errors."""
    cache_key = f"_todos_{workspace_key}"

    if _is_fresh(cache_key):
        return st.session_state[cache_key]

    try:
        ws = _get_todos_sheet()
        records = ws.get_all_records(expected_headers=TODO_COLUMNS)
        todos = [r for r in records if r.get("workspace") == workspace_key]
        _store(cache_key, todos)
        return todos
    except Exception:
        return []


# ─── Write Functions ──────────────────────────────────────────────────────


def generate_project_id(workspace_key: str) -> str:
    now = datetime.now(timezone.utc)
    prefix = workspace_key[:3].upper()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{prefix}-{timestamp}-{suffix}"


def upsert_project(workspace_key: str, project_data: Dict) -> str:
    """Insert or update a project."""
    ws = _get_sheet(workspace_key)
    project_id = project_data.get("project_id")

    if project_id:
        records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
        for idx, row in enumerate(records, start=2):
            if row.get("project_id") == project_id:
                row_data = [project_data.get(col, "") for col in SHEET_COLUMNS]
                ws.update(range_name=f"A{idx}", values=[row_data])
                _clear_cache()
                return project_id

    if not project_id:
        project_id = generate_project_id(workspace_key)
        project_data["project_id"] = project_id

    row_data = [project_data.get(col, "") for col in SHEET_COLUMNS]
    ws.append_row(row_data)
    _clear_cache()
    return project_id


def append_timestamp(workspace_key: str, project_id: str, event: Dict) -> None:
    """Append a timestamp event + update time/status columns."""
    ws = _get_sheet(workspace_key)
    records = ws.get_all_records(expected_headers=SHEET_COLUMNS)

    for idx, row in enumerate(records, start=2):
        if row.get("project_id") == project_id:
            existing_log = row.get("timestamps_log", "")
            try:
                log = json.loads(existing_log) if existing_log else []
            except (json.JSONDecodeError, TypeError):
                log = []
            log.append(event)

            action = event.get("action", "")
            ts = event.get("ts", "")

            # timestamps_log
            col = chr(ord("A") + SHEET_COLUMNS.index("timestamps_log"))
            ws.update(range_name=f"{col}{idx}", values=[[json.dumps(log)]])

            # time column
            time_map = {
                "start": "start_time",
                "pause": "pause_time",
                "resume": "resume_time",
                "complete": "end_time",
            }
            if action in time_map:
                col = chr(ord("A") + SHEET_COLUMNS.index(time_map[action]))
                ws.update(range_name=f"{col}{idx}", values=[[ts]])

            # status column
            status_map = {
                "start": TaskStatus.RUNNING,
                "pause": TaskStatus.PAUSED,
                "resume": TaskStatus.RUNNING,
                "complete": TaskStatus.COMPLETED,
            }
            if action in status_map:
                col = chr(ord("A") + SHEET_COLUMNS.index("status"))
                ws.update(range_name=f"{col}{idx}", values=[[status_map[action]]])

            _clear_cache()
            break


def update_net_duration(workspace_key: str, project_id: str, minutes: float) -> None:
    ws = _get_sheet(workspace_key)
    records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("project_id") == project_id:
            col = chr(ord("A") + SHEET_COLUMNS.index("net_duration_minutes"))
            ws.update(range_name=f"{col}{idx}", values=[[round(minutes, 2)]])
            _clear_cache()
            break


def update_pause_reason(workspace_key: str, project_id: str, reason: str) -> None:
    ws = _get_sheet(workspace_key)
    records = ws.get_all_records(expected_headers=SHEET_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("project_id") == project_id:
            col = chr(ord("A") + SHEET_COLUMNS.index("pause_reason"))
            ws.update(range_name=f"{col}{idx}", values=[[reason]])
            _clear_cache()
            break


def add_todo(workspace_key: str, text: str) -> str:
    todo_id = f"todo-{uuid.uuid4().hex[:8]}"
    ws = _get_todos_sheet()
    ws.append_row([todo_id, text, False, workspace_key])
    _clear_cache()
    return todo_id


def toggle_todo(workspace_key: str, todo_id: str, checked: bool) -> None:
    ws = _get_todos_sheet()
    records = ws.get_all_records(expected_headers=TODO_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("todo_id") == todo_id:
            col = chr(ord("A") + TODO_COLUMNS.index("checked"))
            ws.update(range_name=f"{col}{idx}", values=[[checked]])
            _clear_cache()
            break


def delete_todo(workspace_key: str, todo_id: str) -> None:
    ws = _get_todos_sheet()
    records = ws.get_all_records(expected_headers=TODO_COLUMNS)
    for idx, row in enumerate(records, start=2):
        if row.get("todo_id") == todo_id:
            ws.delete_rows(idx)
            _clear_cache()
            break
