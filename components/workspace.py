"""
Workspace tab renderer.
Renders the full workspace view: status bar, to-do card, project grid, and add form.
"""

from datetime import timedelta
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from auth.google_sheets import read_projects, upsert_project, force_flush
from components.project_card import render_project_card
from components.todo_card import render_todo_card
from config import SHEET_COLUMNS, WORKSPACES, TaskStatus
from logic.state_manager import (
    init_form_state,
    is_form_open,
    toggle_form,
    rebuild_session_from_sheets,
)
from logic.time_tracker import (
    calculate_net_duration,
    format_duration,
    get_status_from_log,
)


def render_workspace(workspace_key: str, is_demo: bool = False) -> None:
    """
    Render the complete workspace view inside a tab.

    Args:
        workspace_key: "samawah" or "kinder"
        is_demo: If True, skip Google Sheets API calls (local testing)
    """
    ws_config = WORKSPACES[workspace_key]
    init_form_state(workspace_key)

    # ── Workspace Header ─────────────────────────────────────
    st.markdown(
        f"""
        <div class="workspace-header" style="background:{ws_config.secondary_color};">
            <span style="font-size:2rem;">{ws_config.icon}</span>
            <h2 style="color:{ws_config.primary_color};">{ws_config.name}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Load Project Data ────────────────────────────────────
    if not is_demo:
        force_flush()  # Flush any pending writes before reading
        projects_df = read_projects(workspace_key)
        # Rebuild session state from Sheets (source of truth)
        if not projects_df.empty:
            rebuild_session_from_sheets(projects_df)
    else:
        projects_df = pd.DataFrame(columns=SHEET_COLUMNS)

    # ── Conditional Auto-Refresh (30s sync when tasks running) ────
    if not is_demo:
        has_running = False
        if not projects_df.empty and "timestamps_log" in projects_df.columns:
            for _, row in projects_df.iterrows():
                log = row.get("timestamps_log", "")
                if isinstance(log, str) and get_status_from_log(log) == "running":
                    has_running = True
                    break

        _auto_interval = timedelta(seconds=30) if has_running else None

        @st.fragment(run_every=_auto_interval)
        def _auto_refresh():
            if has_running:
                st.rerun()

        _auto_refresh()

    # ── Status Overview Bar ──────────────────────────────────
    _render_status_bar(projects_df, ws_config)

    # ── Add New Project Button ───────────────────────────────
    col_add, col_refresh = st.columns([1, 5])
    with col_add:
        if st.button(
            "➕ Add New Project",
            key=f"add_project_{workspace_key}",
            use_container_width=True,
        ):
            toggle_form(workspace_key)
            st.rerun()

    with col_refresh:
        if not is_demo:
            if st.button("🔄 Refresh", key=f"refresh_{workspace_key}"):
                st.cache_data.clear()
                st.rerun()

    # ── Add New Project Form ─────────────────────────────────
    if is_form_open(workspace_key):
        _render_add_form(workspace_key, ws_config, is_demo)

    st.markdown("---")

    # ── General To-Do Card ───────────────────────────────────
    render_todo_card(workspace_key, is_demo)

    st.markdown("---")

    # ── Project Cards Grid ───────────────────────────────────
    if not projects_df.empty:
        st.markdown("### 📋 Projects")

        # Render cards in columns for grid effect
        cards_per_row = 2
        rows = [
            projects_df.iloc[i : i + cards_per_row]
            for i in range(0, len(projects_df), cards_per_row)
        ]

        for row_df in rows:
            cols = st.columns(cards_per_row)
            for idx, (_, project) in enumerate(row_df.iterrows()):
                with cols[idx]:
                    render_project_card(workspace_key, project.to_dict(), is_demo)
    else:
        st.info(f"No projects yet in {ws_config.name}. Add one to get started! 🚀")

    # ── Export Button ────────────────────────────────────────
    if not projects_df.empty and not is_demo:
        st.markdown("---")
        csv = projects_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"📥 Export {ws_config.name} Data as CSV",
            data=csv,
            file_name=f"{workspace_key}_projects.csv",
            mime="text/csv",
            key=f"export_{workspace_key}",
        )


def _render_status_bar(projects_df: pd.DataFrame, ws_config) -> None:
    """Render the live status overview bar with task counts and time."""
    if projects_df.empty:
        return

    # Count by status
    status_counts = (
        projects_df["status"].value_counts().to_dict()
        if "status" in projects_df.columns
        else {}
    )
    running = status_counts.get(TaskStatus.RUNNING, 0)
    paused = status_counts.get(TaskStatus.PAUSED, 0)
    completed = status_counts.get(TaskStatus.COMPLETED, 0)
    idle = status_counts.get(TaskStatus.IDLE, 0)
    total = len(projects_df)

    # Calculate total tracked time
    total_minutes = 0.0
    if "timestamps_log" in projects_df.columns:
        for _, row in projects_df.iterrows():
            log = row.get("timestamps_log", "")
            if isinstance(log, str) and log:
                total_minutes += calculate_net_duration(log)

    completed_pct = int((completed / total * 100) if total > 0 else 0)

    st.markdown(
        f"""
        <div class="status-bar">
            <div class="stat-item">
                <span class="stat-number" style="color:#28a745;">{running}</span>
                <span class="stat-label">Running</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
                <span class="stat-number" style="color:#ffc107;">{paused}</span>
                <span class="stat-label">Paused</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
                <span class="stat-number" style="color:#17a2b8;">{completed}</span>
                <span class="stat-label">Completed</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
                <span class="stat-number">{format_duration(total_minutes)}</span>
                <span class="stat-label">Total Time</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
                <span class="stat-number">{completed_pct}%</span>
                <span class="stat-label">Progress</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mini progress bar
    progress_col, _ = st.columns([3, 1])
    with progress_col:
        st.progress(completed_pct / 100.0)


def _render_add_form(workspace_key: str, ws_config, is_demo: bool) -> None:
    """Render the Add New Project form."""
    st.markdown('<div class="add-form-container">', unsafe_allow_html=True)
    st.markdown("#### 🆕 New Project")

    with st.form(key=f"new_project_form_{workspace_key}"):
        task_desc = st.text_area(
            "Task Description *",
            placeholder="Describe the task...",
            height=80,
        )

        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox(
                "Category",
                options=ws_config.categories,
                index=0,
            )
        with col2:
            doc_link = st.text_input(
                "Document Link (optional)",
                placeholder="https://docs.google.com/...",
            )

        col_submit, col_cancel = st.columns([1, 1])
        with col_submit:
            submitted = st.form_submit_button(
                "✅ Create Project", use_container_width=True
            )
        with col_cancel:
            cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)

        if cancelled:
            toggle_form(workspace_key)
            st.rerun()

        if submitted and task_desc.strip():
            if not is_demo:
                project_data = {
                    "task_description": task_desc.strip(),
                    "category": category,
                    "status": TaskStatus.IDLE,
                    "start_time": "",
                    "pause_time": "",
                    "resume_time": "",
                    "end_time": "",
                    "pause_reason": "",
                    "net_duration_minutes": 0.0,
                    "doc_link": doc_link.strip(),
                    "timestamps_log": "[]",
                }
                upsert_project(workspace_key, project_data)

            toggle_form(workspace_key)
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
