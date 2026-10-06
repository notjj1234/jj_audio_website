"""Streamlit page: Settings — appearance for the desktop app."""

from __future__ import annotations

import streamlit as st

from ui.isolate_state import (
    THEME_MODE_KEY,
    save_theme_state,
)

_MODE_LABELS = {"light": "Light", "dark": "Dark", "system": "System"}


def _persist_theme() -> None:
    # Streamlit calls on_change with no arguments. The widget value is already
    # in session_state, so this wrapper supplies the mapping save_theme_state needs.
    save_theme_state(st.session_state)


def main() -> None:
    st.title("Settings")
    current_mode = st.session_state.get(THEME_MODE_KEY, "dark")
    if current_mode not in _MODE_LABELS:
        current_mode = "dark"
    st.radio(
        "Appearance",
        options=list(_MODE_LABELS.keys()),
        format_func=lambda key: _MODE_LABELS[key],
        index=list(_MODE_LABELS.keys()).index(current_mode),
        key=THEME_MODE_KEY,
        horizontal=True,
        on_change=_persist_theme,
    )
    st.caption("The palette is dark Tyrian blue and yellow-orange.")


if __name__ == "__main__":
    main()
