# Research Summary: Smart Project Tracker v1.1

**Synthesized from:** STACK, FEATURES, ARCHITECTURE, PITFALLS research
**Date:** 2026-04-09

## Stack Additions

**No new Python libraries required.** All four capabilities use existing infrastructure:
- State persistence → Architectural change (write-through to Sheets, store absolute timestamps)
- Cross-device sync → Natural consequence of Sheets-backed state + auto-refresh
- Secrets management → Built-in `st.secrets` (available since Streamlit 0.84)
- Docker → Infrastructure, not application code

**Library change:** Remove `oauth2client` (deprecated since 2020). Use `gspread.service_account_from_dict()` which uses `google-auth` internally (already a transitive dependency of gspread 6.x).

## Key Architecture Decisions

1. **Sheet is source of truth.** `st.session_state` is short-lived cache only.
2. **Live timer via `@st.fragment(run_every="1s")`.** Fragment reruns independently — parent page stays interactive.
3. **Cross-device sync via auto-refresh fragment** every 30 seconds on workspace level.
4. **Absolute timestamps** for timer state (not elapsed duration) — immune to refresh loss.
5. **Last-write-wins** for conflict resolution (safe for single-user app).
6. **Debounced writes** — buffer state changes, flush to Sheets every 5-10 seconds to avoid rate limits.

## Build Order

1. Secrets migration (`google_sheets.py` refactor) — unblocks everything
2. State persistence fix (read pause_reason from sheet on load)
3. Live timer component (`@st.fragment` + auto-refresh)
4. Docker deployment (Dockerfile + docker-compose.yml)

## Critical Pitfalls

| Pitfall | Prevention |
|---------|------------|
| Sheets API 60 req/min limit | Debounce writes, use batch_update |
| Timer blocks UI | Use `@st.fragment`, never `time.sleep` loops |
| secrets.toml format errors | Automate JSON→TOML conversion |
| Docker SSE buffering | Set `X-Accel-Buffering: no` in Nginx |
| Timer drift | Use wall-clock time, not iteration count |

## Files Impact

- **Modify:** `auth/google_sheets.py`, `config.py`, `logic/state_manager.py`, `components/project_card.py`, `components/workspace.py`, `app.py`, `requirements.txt`, `.gitignore`
- **Create:** `.streamlit/secrets.toml` (template), `components/live_timer.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- **Unchanged:** `logic/time_tracker.py`, `components/todo_card.py`, `assets/style.css`

---
*Research synthesized: 2026-04-09*
