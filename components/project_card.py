"""
Project card component.
Renders a single project with status, actions, time tracking, and doc link.
"""

import json
from typing import Dict, Optional

import streamlit as st

from auth.google_sheets import (
    append_timestamp,
    update_net_duration,
    update_pause_reason,
    force_flush,
)
from config import SHEET_COLUMNS, WORKSPACES, TaskStatus
from logic.state_manager import (
    get_pause_reason,
    get_project_status,
    init_project_state,
    set_pause_reason,
    set_project_status,
)
from components.live_timer import render_live_timer
from logic.time_tracker import (
    calculate_net_duration,
    create_event,
    get_status_from_log,
    now_utc_iso,
)


def render_project_card(
    workspace_key: str,
    project: Dict,
    is_demo: bool = False,
) -> None:
    """
    Render a single project card with full interactivity.

    Args:
        workspace_key: "samawah" or "kinder"
        project: Dict with keys matching SHEET_COLUMNS
        is_demo: If True, skip Google Sheets writes (for local testing)
    """
    project_id = project.get("project_id", "unknown")
    task_desc = project.get("task_description", "")
    category = project.get("category", "")
    doc_link = project.get("doc_link", "")
    timestamps_log_raw = project.get("timestamps_log", "")
    pause_reason_saved = project.get("pause_reason", "")

    # Determine current status from sheet data
    sheet_status = get_status_from_log(
        timestamps_log_raw if isinstance(timestamps_log_raw, str) else ""
    )
    net_minutes = calculate_net_duration(
        timestamps_log_raw if isinstance(timestamps_log_raw, str) else ""
    )

    # Initialize session state
    init_project_state(project_id, sheet_status)

    # Use sheet status as source of truth on first load
    current_status = get_project_status(project_id)
    if current_status != sheet_status:
        set_project_status(project_id, sheet_status)
        current_status = sheet_status

    # Card container with status-based border
    border_class = f"card-{current_status}"
    with st.container():
        st.markdown(f'<div class="project-card {border_class}">', unsafe_allow_html=True)

        # ── Card Header: Category badge + Status badge ──────────
        ws_config = WORKSPACES[workspace_key]
        col_header1, col_header2 = st.columns([3, 1])

        with col_header1:
            if category:
                st.markdown(
                    f'<span class="card-category" style="background:{ws_config.secondary_color};color:{ws_config.primary_color};">{category}</span>',
                    unsafe_allow_html=True,
                )

        with col_header2:
            badge_class = f"badge-{current_status}"
            status_label = current_status.upper()
            if current_status == TaskStatus.RUNNING:
                status_label = "▶ RUNNING"
            elif current_status == TaskStatus.PAUSED:
                status_label = "⏸ PAUSED"
            elif current_status == TaskStatus.COMPLETED:
                status_label = "✓ DONE"
            else:
                status_label = "○ IDLE"

            st.markdown(
                f'<span class="card-status-badge {badge_class}">{status_label}</span>',
                unsafe_allow_html=True,
            )

        # ── Task Description ─────────────────────────────────────
        st.markdown(f"**{task_desc}**")

        # ── Duration Display (Live Timer Fragment) ──────────────
        if net_minutes > 0 or current_status == TaskStatus.RUNNING:
            render_live_timer(timestamps_log_raw, current_status)

        # ── Pause Reason (show if paused and has reason) ─────────
        if current_status == TaskStatus.PAUSED and pause_reason_saved:
            st.markdown(
                f'<div class="pause-reason-container">📝 Pause reason: {pause_reason_saved}</div>',
                unsafe_allow_html=True,
            )

        # ── Doc Link ─────────────────────────────────────────────
        if doc_link:
            st.markdown(
                f'<a class="doc-link" href="{doc_link}" target="_blank">📎 Open Document</a>',
                unsafe_allow_html=True,
            )

        # ── Action Buttons ───────────────────────────────────────
        visibility = TaskStatus.button_visibility(current_status)

        if any(visibility.values()):
            st.markdown('<div class="action-buttons">', unsafe_allow_html=True)
            btn_cols = st.columns(4)
            button_idx = 0

            if visibility.get("start"):
                with btn_cols[button_idx]:
                    if st.button("▶ Start", key=f"start_{project_id}", type="primary"):
                        _handle_action(
                            workspace_key, project_id, "start", is_demo
                        )
                button_idx += 1

            if visibility.get("pause"):
                # Show pause reason input inline
                with btn_cols[button_idx]:
                    if st.button("⏸ Pause", key=f"pause_{project_id}"):
                        _handle_action(
                            workspace_key, project_id, "pause", is_demo
                        )
                button_idx += 1

            if visibility.get("resume"):
                with btn_cols[button_idx]:
                    if st.button("▶ Resume", key=f"resume_{project_id}"):
                        _handle_action(
                            workspace_key, project_id, "resume", is_demo
                        )
                button_idx += 1

            if visibility.get("complete"):
                with btn_cols[button_idx]:
                    if st.button("✓ Complete", key=f"complete_{project_id}"):
                        _handle_action(
                            workspace_key, project_id, "complete", is_demo
                        )
                button_idx += 1

            st.markdown("</div>", unsafe_allow_html=True)

            # Pause reason input (show when pause button is visible)
            if visibility.get("pause"):
                reason = st.text_input(
                    "Pause reason (optional)",
                    value=get_pause_reason(project_id),
                    key=f"pause_reason_input_{project_id}",
                    placeholder="Why are you pausing?",
                )
                set_pause_reason(project_id, reason)

        st.markdown("</div>", unsafe_allow_html=True)


def _handle_action(
    workspace_key: str,
    project_id: str,
    action: str,
    is_demo: bool,
) -> None:
    """Handle a button action: update status, record timestamp, sync to sheets."""

    event = create_event(action)

    if not is_demo:
        # Write to Google Sheets
        append_timestamp(workspace_key, project_id, event)
        force_flush()  # Ensure write is persisted before any read

        # If completing, calculate and save net duration
        if action == "complete":
            from auth.google_sheets import read_projects

            # Read back the updated log to calculate duration
            import time
            time.sleep(0.5)  # Brief delay for sheet propagation
            df = read_projects(workspace_key)
            row = df[df["project_id"] == project_id]
            if not row.empty:
                log_str = row.iloc[0].get("timestamps_log", "")
                net = calculate_net_duration(log_str)
                update_net_duration(workspace_key, project_id, net)

        # If pausing, save the pause reason
        if action == "pause":
            reason = get_pause_reason(project_id)
            if reason:
                update_pause_reason(workspace_key, project_id, reason)

    # Update session state
    new_status = {
        "start": TaskStatus.RUNNING,
        "pause": TaskStatus.PAUSED,
        "resume": TaskStatus.RUNNING,
        "complete": TaskStatus.COMPLETED,
    }.get(action, TaskStatus.IDLE)
    set_project_status(project_id, new_status)

    # Trigger page rerun to refresh the UI
    st.rerun()
