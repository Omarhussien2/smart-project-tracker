# Phase 7: State Persistence - Research

**Researched:** 2026-04-09
**Confidence:** HIGH

## Summary

Phase 7 makes Google Sheets the single source of truth. Currently, `state_manager.py` stores everything in `st.session_state` which dies on refresh. The fix: on every page load, read project data from Sheets and reconstruct session state from it. Add debounced writes to stay under 60 req/min API limit.

## Key Findings

1. **state_manager.py** only uses `st.session_state` — all state dies on refresh. Must add `rebuild_session_state()` that reads from Sheets DataFrame.
2. **project_card.py** already derives status from `timestamps_log` via `get_status_from_log()` — this is good, Sheets already has the data.
3. **project_card.py** pause reason comes from `project["pause_reason"]` (Sheets column) AND `get_pause_reason()` (session state). The session state version overwrites. Need to prefer Sheets data.
4. **Each `get_client()` call** creates a new gspread client — no caching. Debounce writes to batch rapid start→pause→resume sequences.
5. **No accumulated_seconds column** exists in SHEET_COLUMNS — elapsed time is computed from `timestamps_log` via `calculate_net_duration()` which already handles "currently running" intervals.

## Architecture

### Pattern 1: Rebuild Session State on Load
In `workspace.py`, after reading `projects_df` from Sheets, iterate rows and call `init_project_state()` + `set_project_status()` with the correct status from `get_status_from_log()`. Also restore pause reasons.

### Pattern 2: Debounced Write Wrapper
Add `auth/google_sheets.py` wrapper that buffers writes and flushes on a timer. Use a simple dict buffer + last_flush timestamp. Flush when buffer age > DEBOUNCE_INTERVAL or on explicit flush call.

### Pattern 3: Config Constant
Add `DEBOUNCE_INTERVAL_SECONDS = 5` to `config.py`.

## Files Impact

| File | Change |
|------|--------|
| `logic/state_manager.py` | Add `rebuild_session_from_sheets()` |
| `components/workspace.py` | Call rebuild after loading data |
| `components/project_card.py` | Prefer Sheets pause_reason over session state |
| `auth/google_sheets.py` | Add debounced write wrapper |
| `config.py` | Add DEBOUNCE_INTERVAL_SECONDS |

## Pitfalls

1. **Race condition on rapid actions**: start→pause within 1s must not lose data. Debounce batches writes but individual `append_timestamp` calls are atomic — each call is a full API round-trip. Debouncing helps by coalescing multiple column updates into one batch.
2. **Stale session state after rebuild**: Must ensure `rebuild_session_from_sheets()` runs BEFORE `render_project_card()` so cards see correct state.
3. **calculate_net_duration already handles "running"**: It adds `(now - last_start/resume)` for open intervals. This means elapsed time is always correct even without accumulated_seconds column.
