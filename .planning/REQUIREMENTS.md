# Requirements: Smart Project Tracker v1.1

**Defined:** 2026-04-09
**Core Value:** Never lose tracked time — every second of work is captured, persisted, and synchronized across devices instantly.

## v1.1 Requirements

### Secrets Management

- [ ] **SECR-01**: App loads Google API credentials from `.streamlit/secrets.toml` instead of `credentials.json` file
- [ ] **SECR-02**: App uses `gspread.service_account_from_dict()` directly, removing the deprecated `oauth2client` dependency entirely
- [ ] **SECR-03**: App detects missing secrets and shows a clear "Demo Mode" banner with setup instructions instead of crashing

### State Persistence

- [ ] **PERS-01**: Timer state survives page refresh — running timers continue from the correct elapsed time after F5/refresh with zero data loss
- [ ] **PERS-02**: Pause reason text persists across page refreshes by reading it back from the Google Sheets `pause_reason` column on load
- [ ] **PERS-03**: Dashboard reads the latest project state from Google Sheets on every load, ensuring fresh data regardless of device
- [ ] **PERS-04**: All write operations to Google Sheets are debounced (buffered and flushed in batches) to stay under the 60 req/min API rate limit

### Live Timer

- [ ] **TMER-01**: Running task cards show a live ticking elapsed time counter that updates every second without blocking other UI interactions
- [ ] **TMER-02**: Timer state syncs across devices (laptop/mobile) within 30 seconds via auto-refresh from Google Sheets
- [ ] **TMER-03**: Workspace auto-refreshes project data from Sheets every 30 seconds when running tasks exist (no refresh when idle)

### Deployment

- [ ] **DEPL-01**: App deploys via `docker compose up -d --build` with a production-ready Dockerfile and Docker Compose configuration
- [ ] **DEPL-02**: Nginx reverse proxy handles SSL termination, WebSocket/SSE proxying with `X-Accel-Buffering: no`, and blocks access to secrets
- [ ] **DEPL-03**: Docker container includes health check monitoring via `/_stcore/health` endpoint with automatic restart on failure
- [ ] **DEPL-04**: Production deployment uses structured error-level logging with log rotation to prevent unbounded log growth from timer refreshes

## v2 Requirements (Deferred)

### Performance & Polish

- **PERF-01**: Client-side JavaScript ticking counter for sub-second visual smoothness (server fragment handles accuracy)
- **PERF-02**: Batch multiple cell updates into a single Sheets API call using `spreadsheets.values.batchUpdate`
- **PERF-03**: Connection status indicator showing live/offline state with automatic write retry queue

### Advanced Features

- **ADV-01**: Keyboard shortcuts for Start/Pause/Resume/Complete actions
- **ADV-02**: Export workspace data as PDF report with time summaries
- **ADV-03**: Email notifications when long-running tasks exceed a threshold

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user authentication | Single user app — no auth system needed |
| Real-time WebSocket push | Over-engineered for single user; polling is sufficient |
| SQLite/PostgreSQL migration | Google Sheets is the chosen and preferred backend |
| Offline mode | Always-connected assumption; too complex for single-user tracker |
| Native mobile app | Responsive web is sufficient |
| Real-time database (Firebase/Supabase) | Would require rewrite of entire backend layer |
| Multi-stage Docker build | No build step to optimize; adds complexity for zero benefit |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SECR-01 | Phase 6 | Pending |
| SECR-02 | Phase 6 | Pending |
| SECR-03 | Phase 6 | Pending |
| PERS-01 | Phase 7 | Pending |
| PERS-02 | Phase 7 | Pending |
| PERS-03 | Phase 7 | Pending |
| PERS-04 | Phase 7 | Pending |
| TMER-01 | Phase 8 | Pending |
| TMER-02 | Phase 8 | Pending |
| TMER-03 | Phase 8 | Pending |
| DEPL-01 | Phase 9 | Pending |
| DEPL-02 | Phase 9 | Pending |
| DEPL-03 | Phase 9 | Pending |
| DEPL-04 | Phase 9 | Pending |

**Coverage:**
- v1.1 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-09*
*Last updated: 2026-04-09 after milestone v1.1 definition*
