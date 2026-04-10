"""
Smart Project Tracker Dashboard
────────────────────────────────
Main Streamlit application entry point.
Two isolated workspaces: Samawah (corporate) + Kinder Market (personal)
Google Sheets as live backend.
"""

import os
import streamlit as st

from components.workspace import render_workspace
from config import APP_ICON, APP_TITLE, WORKSPACES

# ─── Page Configuration ──────────────────────────────────────────────────

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Load Custom CSS ─────────────────────────────────────────────────────

css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ─── App Title ───────────────────────────────────────────────────────────

st.markdown(
    f"""
    <div style="text-align:center; padding: 10px 0 20px 0;">
        <h1>{APP_ICON} {APP_TITLE}</h1>
        <p style="color:#6c757d; font-size:0.9rem;">
            Track your projects with smart time tracking • Live sync with Google Sheets
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Check for credentials ───────────────────────────────────────────────

from config import has_google_credentials

is_demo = not has_google_credentials()

# If credentials exist, verify they actually work
_sheets_error = None
if not is_demo:
    from auth.google_sheets import test_connection

    _ok, _msg = test_connection()
    if not _ok:
        is_demo = True
        _sheets_error = _msg

if _sheets_error:
    st.error(
        f"🔴 **Google Sheets Connection Failed**\n\n{_msg}\n\n"
        "The app is running in **offline mode** until this is fixed."
    )
elif is_demo:
    st.warning(
        "⚠️ **Demo Mode** — Google credentials not found. "
        "Google Sheets integration is disabled.\n\n"
        "**To enable:** Create `.streamlit/secrets.toml` with your Google Service Account credentials. "
        "See the template in `.streamlit/secrets.toml` for the required format."
    )

# ─── Dark/Light Mode Toggle ──────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    dark_mode = st.toggle("🌙 Dark Mode", value=False)

    if dark_mode:
        st.markdown(
            """
            <style>
            .stApp { background: #1a1a2e; color: #e9ecef; }
            .project-card { background: #16213e; border-color: #2d3a5c; }
            .todo-card { background: #16213e; border-color: #2d3a5c; }
            .status-bar { background: #16213e; border-color: #2d3a5c; }
            .add-form-container { background: #16213e; border-color: #2d3a5c; }
            .stTextArea > div > div > textarea,
            .stTextInput > div > div > input {
                background: #0f3460 !important;
                color: #e9ecef !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### ⌨️ Keyboard Shortcuts")
    st.caption("• **R** — Refresh data")
    st.caption("• **N** — New project")

    st.markdown("---")
    st.markdown(
        f"<div style='text-align:center; color:#6c757d; font-size:0.75rem;'>"
        f"{APP_TITLE} v1.1<br/>"
        f"Built with Streamlit + Google Sheets"
        f"</div>",
        unsafe_allow_html=True,
    )

# ─── Workspace Tabs ──────────────────────────────────────────────────────

tab_labels = [
    f"{WORKSPACES['samawah'].icon} {WORKSPACES['samawah'].name}",
    f"{WORKSPACES['kinder'].icon} {WORKSPACES['kinder'].name}",
]

tab_samawah, tab_kinder = st.tabs(tab_labels)

with tab_samawah:
    render_workspace("samawah", is_demo=is_demo)

with tab_kinder:
    render_workspace("kinder", is_demo=is_demo)

# ─── Footer ──────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="text-align:center; padding: 20px 0 10px 0; color:#adb5bd; font-size:0.75rem;">
        Smart Project Tracker • Data synced with Google Sheets every 30 seconds
    </div>
    """,
    unsafe_allow_html=True,
)
