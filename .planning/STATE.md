# Project State

## Current Position

**Phase:** Phase 8 — Live Timer
**Plan:** 08-01 (Complete)
**Status:** Plan 01 complete, ready for 08-02
**Last activity:** 2026-04-09 — Completed 08-01 live timer fragment

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-09)

**Core value:** Never lose tracked time — every second of work is captured, persisted, and synchronized across devices instantly.
**Current focus:** v1.1 — Phase 8: Live Timer

## v1.1 Roadmap

| Phase | Name | Requirements | Status |
|-------|------|-------------|--------|
| 6 | Secrets Management | SECR-01, SECR-02, SECR-03 | Complete |
| 7 | State Persistence | PERS-01, PERS-02, PERS-03, PERS-04 | Complete |
| 8 | Live Timer | TMER-01, TMER-02, TMER-03 | In Progress (Plan 1/2 complete) |
| 9 | Docker Deployment | DEPL-01, DEPL-02, DEPL-03, DEPL-04 | Blocked by Phase 8 |

## Accumulated Context

### From v1.0
- Google Sheets backend works reliably with gspread
- Streamlit session state is the main pain point for persistence
- Two-workspace model (Samawah/Kinder) is well-received
- Custom CSS provides good visual polish
- Demo mode is useful for testing without credentials

### From Phase 8 Plan 1
- @st.fragment(run_every=timedelta(seconds=1)) for per-second UI updates
- Fragment reads only frozen timestamps_log parameter — zero Sheets API calls on tick
- CSS .live-timer-running class reuses existing @keyframes pulse animation
- calculate_net_duration() handles open intervals with (now - interval_start) for ticking effect

## Decisions Log

| Decision | Phase | Summary | Rationale |
|----------|-------|---------|-----------|
| Google Sheets backend | v1.0 | Use gspread + service account | User prefers spreadsheet interface |
| Streamlit framework | v1.0 | Python web framework for dashboard | Fast development, good enough |
| Docker deployment | v1.1 | Containerize with Docker Compose | Easier management and updates |
| Live ticking timer | v1.1 | Real-time stopwatch on running cards | Better UX during active work |
| Full cross-device parity | v1.1 | Identical experience on all devices | User switches laptop/mobile |
| Fixed 1s fragment run_every | 08-01 | No dynamic toggle at component level | Plan 02 handles workspace-level lifecycle |
| No API calls in fragment | 08-01 | Only read from in-memory timestamps_log | Zero Sheets API calls per tick |

## Blockers

(None currently)

## Session Info

**Stopped at:** Completed 08-01-PLAN.md
**Last session:** 2026-04-09T20:09:29Z
