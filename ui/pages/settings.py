"""Streamlit page: Settings — appearance for the desktop app."""

from __future__ import annotations

import json

import streamlit as st

from ui.isolate_state import (
    THEME_CUSTOM_TOKENS_KEY,
    THEME_MODE_KEY,
    THEME_PRESET_KEY,
    save_theme_state,
)

_MODE_LABELS = {"light": "Light", "dark": "Dark", "system": "System"}

_CUSTOM_GROUPS = {
    "Base layers": [
        ("--custom-bg-deepest", "Deepest background", "#192542"),
        ("--custom-bg-deep", "Panel background", "#192542"),
        ("--custom-bg-raised", "Raised background", "#2A4467"),
        ("--custom-bg-highlight", "Highlight background", "#2A4467"),
    ],
    "Text": [
        ("--custom-text-primary", "Primary text", "#f6ad49"),
        ("--custom-text-secondary", "Secondary text", "#f6ad49"),
        ("--custom-text-muted", "Muted text", "#FFAB0F"),
    ],
    "Accents": [
        ("--custom-accent-primary", "Primary accent", "#f6ad49"),
        ("--custom-accent-primary-hover", "Primary accent hover", "#FFAB0F"),
        ("--custom-accent-secondary", "Secondary accent", "#f6ad49"),
        ("--custom-accent-secondary-hover", "Secondary accent hover", "#FFAB0F"),
        ("--custom-accent-tertiary", "Tertiary accent", "#192542"),
        ("--custom-accent-tertiary-hover", "Tertiary accent hover", "#2A4467"),
    ],
}


def _persist_theme() -> None:
    # Streamlit calls on_change with no arguments. The widget value is already
    # in session_state, so this wrapper supplies the mapping save_theme_state needs.
    save_theme_state(st.session_state)


def _render_custom_colors() -> None:
    st.caption("Adjust colors. Changes apply on the next run.")
    custom_tokens = st.session_state.get(THEME_CUSTOM_TOKENS_KEY, {})
    if not isinstance(custom_tokens, dict):
        custom_tokens = {}
    for group_name, tokens in _CUSTOM_GROUPS.items():
        with st.expander(group_name, expanded=(group_name == "Accents")):
            for key, label, default in tokens:
                current_val = custom_tokens.get(key, default)
                if not isinstance(current_val, str) or not current_val.startswith("#"):
                    current_val = default
                new_val = st.color_picker(label, value=current_val, key=f"theme_{key}")
                if new_val != current_val:
                    custom_tokens[key] = new_val
                    st.session_state[THEME_CUSTOM_TOKENS_KEY] = custom_tokens
                    save_theme_state(st.session_state)
                    st.rerun()
    reset_col, export_col, import_col = st.columns(3)
    with reset_col:
        if st.button("Reset custom colors"):
            st.session_state[THEME_CUSTOM_TOKENS_KEY] = {}
            save_theme_state(st.session_state)
            st.rerun()
    with export_col:
        if st.button("Export JSON"):
            st.code(json.dumps(custom_tokens, indent=2), language="json")
    with import_col:
        uploaded = st.file_uploader("Import", type=["json"], label_visibility="collapsed")
        if uploaded:
            try:
                imported = json.load(uploaded)
            except Exception:
                st.error("Invalid theme file")
            else:
                if isinstance(imported, dict):
                    st.session_state[THEME_CUSTOM_TOKENS_KEY] = imported
                    save_theme_state(st.session_state)
                    st.rerun()
                else:
                    st.error("Invalid theme file")


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
    if st.button("Use default colors"):
        st.session_state[THEME_PRESET_KEY] = "tyrian"
        st.session_state[THEME_CUSTOM_TOKENS_KEY] = {}
        save_theme_state(st.session_state)
        st.rerun()
    if st.session_state.get(THEME_PRESET_KEY) == "custom":
        st.subheader("Custom colors")
        _render_custom_colors()


if __name__ == "__main__":
    main()
