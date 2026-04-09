# Smart Project Tracker Dashboard

## What This Is

An interactive project management dashboard built with Streamlit, featuring two isolated workspaces — "Samawah" for corporate work and "Kinder Market" for personal work. Uses card-based UI with smart time tracking (auto-timestamps with pause/resume cycles) and Google Sheets as a live backend. Designed for a single power user who switches between laptop and mobile throughout the day.

## Core Value

Never lose tracked time — every second of work is captured, persisted, and synchronized across devices instantly.

## Requirements

### Validated

<!-- Shipped in v1.0 — confirmed working -->

- ✓ Two isolated workspace tabs (Samawah corporate, Kinder Market personal) — v1.0
- ✓ Project cards with task description, category, and doc link — v1.0
- ✓ Smart time tracking: Start → Pause (with reason) → Resume → Complete — v1.0
- ✓ Net duration calculation handling multiple pause/resume cycles — v1.0
- ✓ Google Sheets as live backend (gspread + service account auth) — v1.0
- ✓ Status overview bar with running/paused/completed counts and progress — v1.0
- ✓ General To-Do lists per workspace — v1.0
- ✓ Dark/Light mode toggle — v1.0
- ✓ CSV export per workspace — v1.0
- ✓ Color-coded card borders by status (green=running, yellow=paused, gray=idle, blue=done) — v1.0
- ✓ Custom CSS with hover effects, animations, RTL support — v1.0

### Active

<!-- Milestone v1.1 scope -->

- [ ] Timer state persists across page refreshes (no data loss)
- [ ] Cross-device sync — full read/write from any device
- [ ] Google API credentials stored securely via Streamlit secrets
- [ ] Docker-based deployment on Hostinger VPS
- [ ] Live ticking elapsed time on running task cards

### Out of Scope

- Multi-user authentication — single user app
- Real-time collaboration — one user, multiple devices
- Offline mode — always connected to Google Sheets
- Native mobile app — responsive web is sufficient
- Database migration (SQL/PostgreSQL) — Google Sheets is the chosen backend

## Context

- **Tech stack:** Python 3.11, Streamlit, gspread, oauth2client, pandas
- **Backend:** Google Sheets (3 sheets: samawah_projects, kinder_projects, todos)
- **Deployment target:** Hostinger VPS with Docker + Nginx reverse proxy
- **Key challenge:** Streamlit's session state is in-memory only — page refresh destroys running timer state. This is the #1 pain point.
- **Current auth:** Service account JSON file (credentials.json) — needs to move to secrets.toml
- **Cross-device:** User switches between laptop and mobile; needs identical experience

## Constraints

- **Backend:** Google Sheets — non-negotiable, user prefers spreadsheet interface
- **Framework:** Streamlit — already built on it, not switching
- **Hosting:** Hostinger VPS — already provisioned
- **Security:** Never commit API credentials to git — use secrets.toml
- **Single user:** No auth system needed, but credentials must be secure

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Google Sheets as backend | User wants spreadsheet interface + free tier | ✓ Good |
| Streamlit for UI | Fast prototyping, Python-native, good enough for single user | ✓ Good |
| Service account auth | No user login needed, direct API access | ⚠️ Revisit — move to secrets.toml |
| In-memory session state | Streamlit default — causes data loss on refresh | ⚠️ Revisit — main pain point |
| Two separate sheets | Clean workspace isolation | ✓ Good |

---
*Last updated: 2026-04-09 after v1.1 milestone initialization*
