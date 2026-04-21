"""
Smart Project Tracker Dashboard
────────────────────────────────
Main Streamlit application entry point.
Two isolated workspaces: Samawah (corporate) + Kinder Market (personal)
Google Sheets as live backend.
"""

import os
import traceback

import streamlit as st

# ─── Page Configuration ──────────────────────────────────────────────────

st.set_page_config(
    page_title="Smart Project Tracker",
    page_icon="📊",
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
    """
    <div style="text-align:center; padding: 10px 0 20px 0;">
        <h1>📊 Smart Project Tracker</h1>
        <p style="color:#6c757d; font-size:0.9rem;">
            Track your projects with smart time tracking • Live sync with Google Sheets
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Safe Import Zone ────────────────────────────────────────────────────
# Everything below is wrapped in try/except so the page ALWAYS renders.

_init_error = None

try:
    from config import APP_TITLE, WORKSPACES, has_google_credentials

    is_demo = not has_google_credentials()

    if is_demo:
        st.warning(
            "⚠️ **Demo Mode** — Google credentials not found. "
            "Google Sheets integration is disabled.\n\n"
            "**To enable:** Add your Google Service Account credentials to "
            "Streamlit Cloud secrets or `.streamlit/secrets.toml`."
        )

    from components.workspace import render_workspace

except Exception as e:
    _init_error = f"Init error: `{e}`\n\n```\n{traceback.format_exc()}\n```"
    is_demo = True

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
        "<div style='text-align:center; color:#6c757d; font-size:0.75rem;'>"
        "Smart Project Tracker v1.1<br/>"
        "Built with Streamlit + Google Sheets"
        "</div>",
        unsafe_allow_html=True,
    )

# ─── Show init error if imports failed ───────────────────────────────────

if _init_error:
    st.error(f"🔴 **Failed to initialize:**\n\n{_init_error}")
    st.info("Check the Streamlit Cloud logs for details.")
    st.stop()

# ─── Workspace Tabs ──────────────────────────────────────────────────────

tab_labels = [
    f"{WORKSPACES['samawah'].icon} {WORKSPACES['samawah'].name}",
    f"{WORKSPACES['kinder'].icon} {WORKSPACES['kinder'].name}",
]

tab_samawah, tab_kinder = st.tabs(tab_labels)

with tab_samawah:
    try:
        render_workspace("samawah", is_demo=is_demo)
    except Exception as e:
        st.error(f"🔴 Error loading Samawah: `{e}`")

with tab_kinder:
    try:
        render_workspace("kinder", is_demo=is_demo)
    except Exception as e:
        st.error(f"🔴 Error loading Kinder Market: `{e}`")

# ─── Footer ──────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="text-align:center; padding: 20px 0 10px 0; color:#adb5bd; font-size:0.75rem;">
        Smart Project Tracker • Data synced with Google Sheets every 30 seconds
    </div>
    """,
    unsafe_allow_html=True,
)
