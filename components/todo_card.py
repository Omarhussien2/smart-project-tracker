"""
To-Do card component.
Renders a simple checklist with add/remove/toggle functionality.
"""

from typing import Dict, List

import streamlit as st

from auth.google_sheets import add_todo, delete_todo, read_todos, toggle_todo
from config import WORKSPACES


def render_todo_card(workspace_key: str, is_demo: bool = False) -> None:
    """
    Render the General To-Do card for a workspace.

    Args:
        workspace_key: "samawah" or "kinder"
        is_demo: If True, skip Google Sheets writes
    """
    ws_config = WORKSPACES[workspace_key]

    st.markdown('<div class="todo-card">', unsafe_allow_html=True)
    st.markdown(f"#### ✅ General To-Do — {ws_config.name}")

    # Add new to-do
    new_todo_col, btn_col = st.columns([4, 1])
    with new_todo_col:
        new_text = st.text_input(
            "Add a to-do item",
            key=f"new_todo_{workspace_key}",
            placeholder="Type a task and press Add...",
            label_visibility="collapsed",
        )
    with btn_col:
        if st.button("➕ Add", key=f"add_todo_btn_{workspace_key}"):
            if new_text.strip() and not is_demo:
                add_todo(workspace_key, new_text.strip())
                st.rerun()

    # Render existing to-dos
    if not is_demo:
        todos = read_todos(workspace_key)
    else:
        todos = []

    if todos:
        st.markdown("---")
        for todo in todos:
            todo_id = todo.get("todo_id", "")
            text = todo.get("text", "")
            checked = todo.get("checked", False)

            col_check, col_text, col_del = st.columns([1, 8, 1])

            with col_check:
                is_checked = st.checkbox(
                    "✓",
                    value=checked,
                    key=f"todo_check_{todo_id}",
                    label_visibility="collapsed",
                )
                if is_checked != checked and not is_demo:
                    toggle_todo(workspace_key, todo_id, is_checked)

            with col_text:
                if is_checked:
                    st.markdown(
                        f'<span class="todo-item checked">{text}</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"• {text}")

            with col_del:
                if st.button("🗑", key=f"del_todo_{todo_id}"):
                    if not is_demo:
                        delete_todo(workspace_key, todo_id)
                        st.rerun()
    else:
        st.caption("No to-do items yet. Add one above!")

    st.markdown("</div>", unsafe_allow_html=True)
