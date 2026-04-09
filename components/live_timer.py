"""
Live timer fragment component.
Renders a ticking elapsed time display for running task cards.
Uses @st.fragment(run_every=1s) to re-render every second without full page rerun.
"""

from datetime import timedelta

import streamlit as st

from logic.time_tracker import calculate_net_duration, format_duration


@st.fragment(run_every=timedelta(seconds=1))
def render_live_timer(timestamps_log: str, status: str) -> None:
    """
    Render a live-updating elapsed time display.

    For running tasks: re-renders every second with updated duration.
    calculate_net_duration() computes (now - interval_start) for open intervals,
    so each re-render shows the incremented time — creating the ticking effect.

    For non-running tasks: still re-renders every second (fragment behavior),
    but displays the same static value since the timestamps_log is frozen
    between full reruns. This is correct and harmless.

    Args:
        timestamps_log: JSON string of timestamp events (frozen between full reruns)
        status: Current task status ("running", "paused", "completed", "idle")
    """
    net_minutes = calculate_net_duration(timestamps_log)
    duration_str = format_duration(net_minutes)

    if status == "running":
        st.markdown(
            f'<div class="duration-display live-timer-running">⏱ {duration_str}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="duration-display">⏱ {duration_str}</div>',
            unsafe_allow_html=True,
        )
