"""Streamlit page: Settings — appearance + legal / local data (compliance)."""

from __future__ import annotations

import streamlit as st

from ui.common import DATA_DIR, clear_all_local_runs, legal_docs_dir
from ui.studio_panel import render_library_tools
from ui.isolate_state import (
    THEME_MODE_KEY,
    save_theme_state,
)

_MODE_LABELS = {"light": "Light", "dark": "Dark", "system": "System"}

_LEGAL_FILES = (
    ("Privacy policy", "privacy.md"),
    ("Terms of service", "terms.md"),
    ("Refund policy", "refund.md"),
    ("Cookie policy", "cookies.md"),
    ("Notices (fonts & images)", "NOTICES.md"),
    ("Third-party SDKs", "THIRD_PARTY_SDKS.md"),
)
_LEGAL_TITLES = [title for title, _ in _LEGAL_FILES]
_LEGAL_BY_TITLE = {title: filename for title, filename in _LEGAL_FILES}


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

    st.divider()
    st.subheader("Local data")
    st.caption(
        f"Run outputs and uploads for this Desktop UI live under `{DATA_DIR}`. "
        "Clearing deletes those run folders only (not your original music library)."
    )
    confirm = st.checkbox(
        "I understand this permanently deletes local Tab PDF / Isolation run folders",
        value=False,
        key="settings_clear_runs_confirm",
    )
    if st.button(
        "Clear local run data",
        type="secondary",
        disabled=not confirm,
        key="settings_clear_runs",
    ):
        deleted, failed = clear_all_local_runs()
        if failed:
            st.error(f"Cleared {deleted} run folder(s); {failed} could not be removed.")
        else:
            st.success(f"Cleared {deleted} local run folder(s).")

    st.divider()
    render_library_tools()
    st.divider()
    st.subheader("Legal")
    st.caption("Demo draft · not legal advice")
    st.markdown("[orallojohnjames@gmail.com](mailto:orallojohnjames@gmail.com)")

    legal_root = legal_docs_dir()
    if not legal_root.is_dir():
        st.info(
            "Legal markdown was not found next to this install. "
            "See `docs/legal/` in the source repository, or the hosted website Legal pages."
        )
    else:
        with st.expander("View policies", expanded=False):
            selected = st.selectbox(
                "Document",
                options=_LEGAL_TITLES,
                key="settings_legal_doc",
            )
            path = legal_root / _LEGAL_BY_TITLE[selected]
            if path.is_file():
                st.markdown(path.read_text(encoding="utf-8"))
            else:
                st.info(f"That document file is missing ({path.name}).")


if __name__ == "__main__":
    main()
