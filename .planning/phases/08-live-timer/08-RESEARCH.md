# Phase 8: Live Timer - Research

**Researched:** 2026-04-09
**Domain:** Streamlit fragments with `run_every` for live-updating UI
**Confidence:** HIGH

## Summary

This phase adds two independent live-update mechanisms using Streamlit's `@st.fragment` API. The first is a per-card elapsed-time counter that ticks every second (TMER-01). The second is a workspace-level conditional auto-refresh that polls Google Sheets every 30 seconds when any task is running (TMER-02, TMER-03).

The core enabling technology is `@st.fragment(run_every=...)`, introduced in Streamlit 1.37.0. The project's `requirements.txt` specifies `streamlit>=1.45`, so fragments are fully available. The `run_every` parameter accepts seconds (int/float), timedelta objects, or Pandas-style strings like `"1s"` or `"30s"`. Critically, `run_every` can be set **dynamically** via a variable — when set to `None`, the fragment stops auto-rerunning. This is the official Streamlit pattern for conditional streaming (verified against the official tutorial "Start and stop a streaming fragment").

The existing `calculate_net_duration()` in `logic/time_tracker.py` already handles "currently running" intervals by computing `(now - last_start/resume)` for open intervals. This means the live timer fragment simply needs to call this function on each tick — no changes to the time calculation logic are needed. The fragment reads the `timestamps_log` from the project data already in session state, avoiding any Google Sheets API calls on the 1-second tick cycle.

**Primary recommendation:** Create a `live_timer` fragment with `run_every=1` that reads from session state (not Sheets), and a workspace-level auto-refresh fragment that dynamically sets `run_every` to 30 seconds only when running tasks exist.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| streamlit | >=1.45 (>=1.37.0 for fragments) | `@st.fragment` with `run_every` | Built-in Streamlit feature; no extra dependencies needed |

### Existing Code (Already Available)
| Module | Function | Purpose | Notes |
|--------|----------|---------|-------|
| `logic/time_tracker.py` | `calculate_net_duration(timestamps_log)` | Computes elapsed minutes including live running intervals | Already handles `(now - last_start/resume)` for open intervals |
| `logic/time_tracker.py` | `format_duration(minutes)` | Formats minutes to "1h 30m 45s" string | Already used in card rendering |
| `logic/time_tracker.py` | `get_status_from_log(timestamps_log)` | Determines status from last log event | Used to check if task is running |
| `auth/google_sheets.py` | `read_projects(workspace_key)` | Reads all project data from Sheets | Used by workspace auto-refresh |
| `logic/state_manager.py` | `rebuild_session_from_sheets(projects_df)` | Rebuilds session state from Sheets data | Already called on every workspace load |

### No New Dependencies Needed
This phase uses only existing Streamlit features and existing project code. No pip installs required.

## Architecture Patterns

### Pattern 1: Per-Card Live Timer Fragment (TMER-01)

**What:** A `@st.fragment(run_every=1)` function that recomputes and displays elapsed time every second for running tasks. Only rendered when a task's status is RUNNING.

**Key principle:** The fragment reads from session state / project data already in memory — it does **NOT** call Google Sheets on every tick. This avoids 1 API call/second/task.

**How it works:**
1. `workspace.py` loads project data from Sheets on full page load
2. `project_card.py` renders each card; for RUNNING tasks, it calls `render_live_timer()` instead of the static duration HTML
3. The live timer fragment reads `timestamps_log` from the passed project data, calls `calculate_net_duration()` which computes `(now - last_start)`, and displays the result
4. The fragment auto-reruns every 1 second, recomputing the elapsed time with the current `now`

**Example:**
```python
# components/live_timer.py
import streamlit as st
from logic.time_tracker import calculate_net_duration, format_duration

@st.fragment(run_every=1)
def render_live_timer(timestamps_log: str) -> None:
    """
    Renders a live-updating elapsed time display for a running task.
    Recomputes every second via fragment auto-rerun.
    Reads timestamps_log from memory — no Sheets API call.
    """
    net_minutes = calculate_net_duration(timestamps_log)
    duration_str = format_duration(net_minutes)
    st.markdown(
        f'<div class="duration-display duration-live">⏱ {duration_str}</div>',
        unsafe_allow_html=True,
    )
```

**Calling from project_card.py:**
```python
# Replace the static duration block (lines 108-113) with:
if current_status == TaskStatus.RUNNING:
    # Live ticking timer for running tasks
    render_live_timer(timestamps_log_raw)
elif net_minutes > 0:
    # Static duration for paused/completed tasks
    duration_str = format_duration(net_minutes)
    st.markdown(
        f'<div class="duration-display">⏱ {duration_str}</div>',
        unsafe_allow_html=True,
    )
```

### Pattern 2: Conditional Workspace Auto-Refresh (TMER-02, TMER-03)

**What:** A fragment at the workspace level that dynamically sets `run_every` to 30 seconds when any task is running, and `None` when all tasks are idle. This ensures cross-device sync within 30 seconds.

**How it works:**
1. Before rendering the workspace content, check if any project has a RUNNING status
2. Set `run_every` variable to 30 if running tasks exist, else `None`
3. Define a fragment decorated with the dynamic `run_every`
4. The fragment reads fresh data from Sheets and updates session state
5. When `run_every=None`, the fragment never auto-reruns — zero unnecessary API calls

**Example:**
```python
# In components/workspace.py
from datetime import timedelta
from config import TaskStatus

def _has_running_tasks(projects_df) -> bool:
    """Check if any task in the DataFrame is currently running."""
    if projects_df.empty or "status" not in projects_df.columns:
        return False
    return TaskStatus.RUNNING in projects_df["status"].values

def render_workspace(workspace_key: str, is_demo: bool = False) -> None:
    # ... existing header code ...

    # Load initial project data
    projects_df = _load_projects(workspace_key, is_demo)

    # Determine if auto-refresh is needed
    auto_refresh = _has_running_tasks(projects_df) and not is_demo
    refresh_interval = 30 if auto_refresh else None

    # Render auto-refresh fragment BEFORE cards
    if auto_refresh:
        _render_auto_refresh(workspace_key)

    # ... rest of workspace rendering ...

@st.fragment(run_every=timedelta(seconds=30))
def _render_auto_refresh(workspace_key: str) -> None:
    """
    Periodically refreshes project data from Sheets when tasks are running.
    Only active when called conditionally based on running task presence.
    """
    force_flush()
    projects_df = read_projects(workspace_key)
    if not projects_df.empty:
        rebuild_session_from_sheets(projects_df)
        st.session_state[f"{workspace_key}_last_refresh"] = datetime.now().isoformat()
```

**IMPORTANT: Dynamic `run_every` pattern (official Streamlit approach):**
```python
# The run_every can be set dynamically via a variable:
run_every = "30s" if has_running_tasks else None

@st.fragment(run_every=run_every)
def auto_refresh():
    # ... refresh logic ...

# But since decorator is evaluated at definition time, use this pattern instead:
# Conditionally CALL the fragment, or use a wrapper approach
```

**Recommended approach for conditional refresh:** Since the `@st.fragment` decorator is evaluated when the function is defined, and `run_every` needs to be dynamic, the cleanest pattern is:
```python
# Check running state before defining/calling fragment
has_running = _has_running_tasks(projects_df)
refresh_every = timedelta(seconds=30) if has_running else None

@st.fragment(run_every=refresh_every)
def _workspace_refresh_fragment():
    force_flush()
    fresh_df = read_projects(workspace_key)
    if not fresh_df.empty:
        rebuild_session_from_sheets(fresh_df)

# Only call if there are running tasks (or always call —
# when run_every=None it just won't auto-rerun)
_workspace_refresh_fragment()
```

### Anti-Patterns to Avoid

- **DON'T call Google Sheets inside a 1-second timer fragment** — This would hit 60+ API calls/minute per running task, exceeding Google's rate limit. The live timer must read from in-memory data only.
- **DON'T put widgets in externally-created containers inside fragments** — Streamlit explicitly forbids this. Widgets must be in the fragment's main body.
- **DON'T use `st.rerun()` inside a fragment to refresh the whole page on every tick** — This defeats the entire purpose of fragments (isolated rerun). Use `st.rerun()` only for deliberate full-page refreshes (e.g., after a button action).
- **DON'T cache (`@st.cache_data`) and fragment the same function** — Streamlit explicitly states this is unsupported.
- **DON'T accumulate elements in outside containers** — If a fragment writes to a container created outside itself, elements accumulate with each fragment rerun. Use the fragment's own main body for rendering.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Auto-updating UI | JavaScript setInterval or meta-refresh hack | `@st.fragment(run_every=N)` | Streamlit's built-in mechanism; handles reconnection, error recovery, and doesn't block interaction |
| Conditional auto-refresh | Custom threading/Timer with state checks | Dynamic `run_every` variable (set to `None` when idle) | Official Streamlit pattern from tutorial; fragment simply doesn't auto-rerun when `run_every=None` |
| Elapsed time calculation for running tasks | Manual time delta tracking in session state | `calculate_net_duration(timestamps_log)` | Already implemented; already handles open intervals by computing `(now - last_start/resume)` |

**Key insight:** The existing `calculate_net_duration()` already computes live elapsed time for running tasks. The function adds `(now - interval_start)` when the last event is `start` or `resume` (line 77-81 of time_tracker.py). This means the 1-second fragment just needs to call this function — zero new time-tracking logic needed.

## Common Pitfalls

### Pitfall 1: Google Sheets Rate Limiting
**What goes wrong:** Calling `read_projects()` on every 1-second tick exceeds Google Sheets API limit (60 req/min for service accounts, or 300 req/min with higher quotas).
**Why it happens:** Putting Sheets reads inside the `run_every=1` fragment.
**How to avoid:** The per-card timer fragment reads ONLY from the `timestamps_log` string already in memory. Only the workspace-level 30-second refresh fragment reads from Sheets.
**Warning signs:** `gspread.exceptions.APIError: 429` in logs, or timer freezing.

### Pitfall 2: Fragment `run_every` Evaluated at Definition Time
**What goes wrong:** Setting `run_every` dynamically doesn't work as expected because the decorator is evaluated when the function is defined, not when it's called.
**Why it happens:** Python decorator syntax `@st.fragment(run_every=X)` evaluates `X` at definition time.
**How to avoid:** Compute `run_every` variable BEFORE the function definition. The variable's value at definition time is what gets used. Re-define or use a conditional wrapper. The official tutorial pattern is to check conditions and set the variable before the `@st.fragment` line.
**Warning signs:** Fragment keeps auto-rerunning even when no tasks are running, or stops when they should be running.

### Pitfall 3: Stale `timestamps_log` in Session State
**What goes wrong:** The live timer shows wrong elapsed time because the `timestamps_log` it reads was from the initial page load, not the current session.
**Why it happens:** If another device starts a timer, the local session state has stale data until a full page rerun or the 30-second refresh happens.
**How to avoid:** The 30-second workspace refresh updates session state, which feeds into the next fragment tick. Accept up to 30-second staleness for cross-device sync (this matches TMER-02's "within 30 seconds" requirement).
**Warning signs:** Timer shows 0 or wrong time after cross-device start; resolves after ~30 seconds.

### Pitfall 4: Multiple Running Tasks Creating Multiple Fragments
**What goes wrong:** Each running task card gets its own `run_every=1` fragment. With 5 running tasks, that's 5 fragments each rerunning every second.
**Why it happens:** Fragment is called per card in the rendering loop.
**How to avoid:** This is actually fine — Streamlit handles multiple independent fragments well, and each only does a lightweight computation (no API calls). But monitor performance if >10 tasks are running simultaneously. Each fragment rerun is cheap (just JSON parse + datetime math + HTML render).
**Warning signs:** Page feels sluggish with many running tasks.

### Pitfall 5: Fragment Renders on Full Rerun Too
**What goes wrong:** On button actions (Start/Pause/etc.), `st.rerun()` triggers a full page rerun. The fragment function gets called again during the full rerun, and then continues auto-rerunning. No actual bug, but understanding this avoids confusion.
**Why it happens:** Fragments execute during full reruns AND during fragment-only reruns.
**How to avoid:** This is expected behavior. The fragment always has current data after a full rerun. No special handling needed.

## Code Examples

### Example 1: Live Timer Fragment (components/live_timer.py)
```python
# Source: Streamlit official docs - st.fragment API
# https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment
"""
Live timer fragment component.
Displays a ticking elapsed time counter for running tasks.
Uses @st.fragment(run_every=1) for per-second updates.
"""

import streamlit as st

from logic.time_tracker import calculate_net_duration, format_duration


@st.fragment(run_every=1)
def render_live_timer(timestamps_log: str) -> None:
    """
    Render a live-updating elapsed time display for a running task.
    
    Auto-reruns every 1 second via Streamlit fragment mechanism.
    Reads timestamps_log from memory — NO Google Sheets API calls.
    
    Args:
        timestamps_log: JSON string of timestamp events from project data
    """
    net_minutes = calculate_net_duration(timestamps_log)
    duration_str = format_duration(net_minutes)
    st.markdown(
        f'<div class="duration-display duration-live">⏱ {duration_str}</div>',
        unsafe_allow_html=True,
    )
```

### Example 2: Integration in project_card.py (replacing static duration)
```python
# In render_project_card(), replace lines 108-113:

# OLD (static):
# if net_minutes > 0 or current_status == TaskStatus.RUNNING:
#     duration_str = format_duration(net_minutes)
#     st.markdown(
#         f'<div class="duration-display">⏱ {duration_str}</div>',
#         unsafe_allow_html=True,
#     )

# NEW (live for running, static for others):
from components.live_timer import render_live_timer

if current_status == TaskStatus.RUNNING:
    # Live ticking counter — updates every second via fragment
    render_live_timer(
        timestamps_log_raw if isinstance(timestamps_log_raw, str) else ""
    )
elif net_minutes > 0:
    # Static display for paused/completed/idle tasks
    duration_str = format_duration(net_minutes)
    st.markdown(
        f'<div class="duration-display">⏱ {duration_str}</div>',
        unsafe_allow_html=True,
    )
```

### Example 3: Conditional Auto-Refresh in workspace.py (TMER-02, TMER-03)
```python
# Source: Streamlit official tutorial - Start and stop a streaming fragment
# https://docs.streamlit.io/develop/tutorials/execution-flow/start-and-stop-fragment-auto-reruns

from datetime import timedelta
from config import TaskStatus, CACHE_TTL_SECONDS

def _has_running_tasks(projects_df) -> bool:
    """Check if any task is currently running."""
    if projects_df.empty or "status" not in projects_df.columns:
        return False
    return TaskStatus.RUNNING in projects_df["status"].values

def render_workspace(workspace_key: str, is_demo: bool = False) -> None:
    # ... existing header code ...

    # Load initial project data (existing code)
    projects_df = _load_initial_data(workspace_key, is_demo)

    # Conditional auto-refresh fragment
    if _has_running_tasks(projects_df) and not is_demo:
        _render_workspace_refresh(workspace_key)

    # ... render status bar, cards, etc. using projects_df ...


@st.fragment(run_every=timedelta(seconds=30))
def _render_workspace_refresh(workspace_key: str) -> None:
    """
    Auto-refreshes workspace data from Sheets every 30 seconds.
    Only called when at least one task is running.
    Triggers full app rerun to refresh all cards with fresh data.
    """
    from auth.google_sheets import read_projects, force_flush
    from logic.state_manager import rebuild_session_from_sheets

    force_flush()
    fresh_df = read_projects(workspace_key)
    if not fresh_df.empty:
        rebuild_session_from_sheets(fresh_df)
    # Trigger full rerun so all cards reflect updated state
    st.rerun()
```

### Example 4: CSS Enhancement for Live Timer (assets/style.css)
```css
/* Live (running) duration display with subtle pulse animation */
.duration-live {
    color: #28a745;  /* Green to match running badge */
    animation: pulse-subtle 1s ease-in-out infinite;
}

@keyframes pulse-subtle {
    0%, 100% { opacity: 1.0; }
    50% { opacity: 0.85; }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `st.empty()` + manual loop with `time.sleep()` | `@st.fragment(run_every=N)` | Streamlit 1.37.0 (Jul 2024) | Fragments are the official way to do live-updating UI; no thread management needed |
| `st_autorefresh` custom component | Built-in `run_every` parameter | Streamlit 1.37.0 | No need for third-party components for auto-refresh |
| Full page rerun for any update | Fragment-only reruns | Streamlit 1.37.0 | Only the fragment re-executes, rest of page is frozen — dramatically better UX |

**Deprecated/outdated:**
- `streamlit-autorefresh` package: Replaced by built-in `run_every` parameter on `@st.fragment`
- Manual `st.empty()` + `while True` + `time.sleep()` pattern: Still works but fragments are cleaner and don't block interaction

## Open Questions

1. **Should the workspace auto-refresh fragment trigger `st.rerun()` after refreshing data?**
   - What we know: The fragment reads fresh data and updates session state, but other UI elements won't update until a full rerun
   - Options: (a) Call `st.rerun()` inside the fragment to force a full refresh every 30s, or (b) Let the fragment-only rerun update the refresh indicator and rely on user interaction to trigger full rerun for card updates
   - Recommendation: Call `st.rerun()` inside the 30-second refresh fragment. This ensures cross-device sync is visible (TMER-02). The cost is a full rerun every 30 seconds only when tasks are running, which is acceptable.

2. **Should the `render_live_timer` fragment receive `timestamps_log` as a parameter or read from session state?**
   - What we know: Fragment parameters are frozen at the time of the full rerun (the decorator captures the call arguments). Session state can change between fragment reruns.
   - Recommendation: Pass `timestamps_log` as a parameter. Since `calculate_net_duration()` computes `(now - interval_start)` using the current time, the passed `timestamps_log` just needs the start/resume events, and the elapsed time will tick correctly. The `timestamps_log` only changes on button actions (start/pause/resume/complete), which trigger full reruns.

3. **How does the fragment handle the transition from running to paused/completed?**
   - What we know: When user clicks Pause or Complete, `_handle_action` calls `st.rerun()` which triggers a full rerun. On full rerun, `project_card.py` re-evaluates status and renders the static duration instead of the live timer fragment.
   - Recommendation: No special handling needed. The full rerun replaces the live timer fragment with static duration display automatically.

## Sources

### Primary (HIGH confidence)
- Streamlit official docs - `st.fragment` API reference: https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment
  - Confirmed: `run_every` accepts int, float, timedelta, string, None
  - Confirmed: `run_every=None` means no auto-rerun (fragment only reruns on widget interaction)
  - Confirmed: Fragments can access session state and imported modules
  - Confirmed: Widgets only in main body of fragment, not externally-created containers
- Streamlit official docs - Working with fragments: https://docs.streamlit.io/develop/concepts/architecture/fragments
  - Confirmed: Fragment execution flow, limitations, comparison with forms/caching
  - Confirmed: Available since Streamlit 1.37.0
- Streamlit official tutorial - Start and stop a streaming fragment: https://docs.streamlit.io/develop/tutorials/execution-flow/start-and-stop-fragment-auto-reruns
  - Confirmed: Dynamic `run_every` pattern — set variable conditionally before function definition
  - Confirmed: When `run_every=None`, fragment stops auto-rerunning

### Codebase Analysis (HIGH confidence)
- `logic/time_tracker.py` lines 60-83: `calculate_net_duration()` handles open intervals by computing `(now - interval_start)` — verified in source
- `components/project_card.py` lines 108-113: Current static duration display — verified in source
- `components/workspace.py` lines 42-48: Current data loading with `read_projects()` + `rebuild_session_from_sheets()` — verified in source
- `config.py` line 113: `CACHE_TTL_SECONDS = 30` — matches TMER-02/03 30-second requirement
- `requirements.txt`: `streamlit>=1.45` — confirmed fragments available (need >=1.37.0)
- `assets/style.css` line 221: `.duration-display` class exists, `.duration-live` needs to be added

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `@st.fragment(run_every=...)` is the official, well-documented Streamlit mechanism for live-updating UI. No alternatives needed.
- Architecture: HIGH — Two-fragment pattern (1s timer + 30s sync) is directly supported by the official Streamlit tutorial. Existing `calculate_net_duration()` already does the right computation.
- Pitfalls: HIGH — Fragment limitations are clearly documented in official docs. Rate limiting concern is straightforward to avoid.
- Integration: HIGH — The changes are surgical: replace static HTML with fragment call in project_card, add conditional refresh call in workspace.

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (Streamlit fragments are stable since 1.37.0; pattern unlikely to change)
