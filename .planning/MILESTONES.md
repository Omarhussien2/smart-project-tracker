# Milestones

## v1.0 — Initial Build ✓

**Date:** 2026-04-09
**Status:** Complete

**Shipped:**
- Two-workspace dashboard (Samawah + Kinder Market)
- Smart time tracking with pause/resume cycles
- Google Sheets backend (CRUD + timestamps)
- Project cards with category, doc link, status badges
- Status overview bar with live counts and progress
- General To-Do lists per workspace
- Dark/Light mode toggle
- CSV export
- Custom CSS (cards, animations, hover effects, RTL)
- Demo mode (works without Google credentials)
- Deployment configs (systemd + nginx)

**Files:** 14 files across 6 modules (app, config, auth, components, logic, deploy)

**Known issues carried forward:**
- Timer state lost on page refresh (Streamlit session state is in-memory)
- No cross-device sync (session state doesn't persist)
- Credentials stored in plaintext JSON file
- No containerized deployment

---
*Next milestone: v1.1 — Stability & Persistence*
