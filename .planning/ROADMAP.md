# Roadmap: Smart Project Tracker v1.1

## Overview

v1.1 hardens the dashboard into a production-grade tool: secrets are managed safely, timer state survives page refreshes and syncs across devices, a live ticking counter provides real-time feedback, and Docker makes deployment a single command. No tracked second is ever lost.

**Build order:** Secrets (foundation) → Persistence (data layer) → Live Timer (UI layer, depends on persistence) → Docker (wraps everything).

---

## Phase Structure

### Phase 6: Secrets Management

**Goal:** Replace plaintext `credentials.json` with Streamlit's native secrets system and eliminate the deprecated `oauth2client` dependency.

**Requirements:** SECR-01, SECR-02, SECR-03

**Depends on:** None (foundation phase)

**Files modified:**
- `auth/google_sheets.py` — rewrite client initialization to use `gspread.service_account_from_dict()`
- `config.py` — load credentials from `st.secrets` instead of file path
- `requirements.txt` — remove `oauth2client`, confirm `gspread` version
- `.gitignore` — add `.streamlit/secrets.toml`

**Files created:**
- `.streamlit/secrets.toml` — template with placeholder credentials and setup instructions

**Success Criteria:**
1. App starts and functions fully in demo mode when `secrets.toml` is absent, showing a visible "Demo Mode" banner with setup instructions
2. App connects to Google Sheets when valid credentials exist in `secrets.toml` — no `credentials.json` file is read anywhere
3. `oauth2client` does not appear anywhere in `requirements.txt` or any source file

**Plans:** 2 plans
- [ ] 06-01-PLAN.md — Core credential migration (config.py helpers + google_sheets.py refactor + requirements.txt)
- [ ] 06-02-PLAN.md — Demo mode detection rewrite + secrets.toml template

---

### Phase 7: State Persistence

**Goal:** Make Google Sheets the single source of truth so timer state, pause reasons, and project data survive page refreshes and work identically across devices.

**Requirements:** PERS-01, PERS-02, PERS-03, PERS-04

**Depends on:** Phase 6 (needs working Sheets connection from secrets)

**Files modified:**
- `auth/google_sheets.py` — add debounced write wrapper, ensure all timer/pause columns are read back
- `logic/state_manager.py` — on every load, rebuild session state from Sheets data instead of starting empty
- `components/workspace.py` — read pause reasons from Sheets on load
- `components/project_card.py` — compute elapsed time from Sheets `start_time` + `accumulated_seconds` instead of session state only
- `config.py` — add debounce interval constant

**Files created:** None

**Success Criteria:**
1. A running timer continues with the correct elapsed time after a full page refresh (F5) — zero seconds lost
2. Pause reason text reappears after refresh by reading it back from the Google Sheets `pause_reason` column
3. Opening the dashboard on a second device shows the latest project states from Sheets (no stale session data)
4. Rapid operations (start → pause → resume within seconds) do not trigger more than one batched write per debounce window

---

### Phase 8: Live Timer

**Goal:** Running task cards display a live ticking elapsed-time counter and auto-sync across devices every 30 seconds.

**Requirements:** TMER-01, TMER-02, TMER-03

**Depends on:** Phase 7 (timer reads elapsed time from persisted state)

**Files modified:**
- `components/project_card.py` — integrate live timer fragment into running cards
- `components/workspace.py` — add conditional auto-refresh when any task is running

**Files created:**
- `components/live_timer.py` — `@st.fragment(run_every="1s")` component that computes and displays elapsed time

**Success Criteria:**
1. A running task card shows an elapsed time counter that visibly ticks every second without freezing or blocking other UI interactions
2. Starting a timer on device A, then opening the dashboard on device B shows the running state within 30 seconds
3. Auto-refresh activates only when at least one task is running and stops when all tasks are idle (no unnecessary API calls)

---

### Phase 9: Docker Deployment

**Goal:** Ship a production-ready containerized deployment that runs with a single `docker compose up` command.

**Requirements:** DEPL-01, DEPL-02, DEPL-03, DEPL-04

**Depends on:** Phase 8 (all app features finalized before containerizing)

**Files modified:**
- `requirements.txt` — pin exact versions for reproducible builds
- `.gitignore` — ensure secrets and cache are excluded

**Files created:**
- `Dockerfile` — single-stage Python build with Streamlit
- `docker-compose.yml` — service definition with health check, restart policy, volume mounts for secrets
- `.dockerignore` — exclude `.git`, `__pycache__`, `.streamlit/secrets.toml`, etc.
- `deploy/nginx.conf` — SSL termination, WebSocket/SSE proxying, secrets blocking

**Success Criteria:**
1. `docker compose up -d --build` starts the app and it is accessible via HTTPS through Nginx
2. Docker health check via `/_stcore/health` detects failures and triggers automatic container restart
3. Nginx blocks all requests to `.streamlit/secrets.toml` and any other sensitive files
4. Logs are written at error level only with rotation configured (no unbounded growth from timer refreshes)

---

## Coverage

| Requirement | Phase | Description |
|-------------|-------|-------------|
| SECR-01 | Phase 6 | Load credentials from `.streamlit/secrets.toml` |
| SECR-02 | Phase 6 | Use `gspread.service_account_from_dict()`, remove `oauth2client` |
| SECR-03 | Phase 6 | Demo Mode banner when secrets are missing |
| PERS-01 | Phase 7 | Timer survives page refresh with zero data loss |
| PERS-02 | Phase 7 | Pause reason persists across refreshes |
| PERS-03 | Phase 7 | Fresh data from Sheets on every load |
| PERS-04 | Phase 7 | Debounced writes under 60 req/min limit |
| TMER-01 | Phase 8 | Live ticking counter every second |
| TMER-02 | Phase 8 | Cross-device sync within 30 seconds |
| TMER-03 | Phase 8 | Auto-refresh only when tasks are running |
| DEPL-01 | Phase 9 | `docker compose up -d --build` deployment |
| DEPL-02 | Phase 9 | Nginx with SSL, WebSocket proxy, secrets blocking |
| DEPL-03 | Phase 9 | Health check with auto-restart |
| DEPL-04 | Phase 9 | Error-level logging with rotation |

**Totals:** 14 requirements → 4 phases, 0 unmapped ✓

---

## Execution Notes

- Each phase should be implemented and tested before moving to the next.
- Phase 6 is safe to merge immediately — it's a pure refactor with no behavioral changes.
- Phase 7 is the highest-risk phase (data migration logic); test refresh scenarios thoroughly.
- Phase 8 depends on Phase 7's persisted elapsed time — do not start before Phase 7 is verified.
- Phase 9 can begin as soon as Phase 8 is complete; the Dockerfile wraps a frozen codebase.

---

*Roadmap created: 2026-04-09*
*Milestone: v1.1 — Stability & Persistence*
