"""Desktop boot screen: launch the real jobs and reopen local separations."""

from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

from ui.common import DATA_DIR, edition_product_name, list_recent_runs
from ui.isolate_jobs import list_jobs, merge_library_runs
from ui.isolate_state import (
    ISOLATE_SKIP_REHYDRATE_KEY,
    ISOLATE_USER_ID_FILENAME,
    LISTEN_PICKER_NEXT_KEY,
    SHELL_TAB_KEY,
    add_open_mix_tab,
    format_source_title,
    infer_source_kind,
    load_persist_isolate_user_id,
    open_home_shell,
    open_mix_shell,
    recent_runs_with_owner_fallback,
)

_HOME_CSS = """
<style>
  .st-key-att_home [data-testid="stButton"] button {
    min-height: 4.6rem;
    border-radius: 14px;
    justify-content: flex-start;
    text-align: left;
    white-space: normal;
    line-height: 1.25;
    transition:
      transform 160ms cubic-bezier(0.22, 1, 0.36, 1),
      border-color 160ms cubic-bezier(0.22, 1, 0.36, 1);
  }
  .st-key-att_home [data-testid="stButton"] button:hover:not(:disabled) {
    border-color: var(--color-accent-primary, #f6ad49);
  }
  @media (prefers-reduced-motion: reduce) {
    .st-key-att_home [data-testid="stButton"] button {
      transition: none;
    }
  }
</style>
"""


def relative_age(created_at: object, *, now: float | None = None) -> str:
    """Short age label for a run timestamp. Unknown times stay blank."""
    try:
        stamp = float(created_at)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if stamp <= 0:
        return ""
    seconds = max(0.0, (time.time() if now is None else float(now)) - stamp)
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return "1 minute ago" if minutes == 1 else f"{minutes} minutes ago"
    hours = int(minutes // 60)
    if hours < 24:
        return "1 hour ago" if hours == 1 else f"{hours} hours ago"
    days = int(hours // 24)
    if days < 30:
        return "1 day ago" if days == 1 else f"{days} days ago"
    months = int(days // 30)
    if months < 12:
        return "1 month ago" if months == 1 else f"{months} months ago"
    years = int(days // 365)
    return "1 year ago" if years <= 1 else f"{years} years ago"


def library_rows(owner: str | None, *, limit: int = 40) -> list[dict]:
    """Isolate runs that still have a wav, newest first. Same owner rule as Isolate."""
    owned = list_recent_runs("isolate", limit=limit, owner=owner)
    everyone = list_recent_runs("isolate", limit=limit)
    recent = recent_runs_with_owner_fallback(owned, everyone)
    merged = merge_library_runs(recent, list_jobs(limit=limit))
    usable: list[dict] = []
    for row in merged:
        arts = row.get("artifacts") or {}
        if not isinstance(arts, dict):
            continue
        if any(str(path).lower().endswith(".wav") for path in arts.values()):
            usable.append(row)
    return usable[:limit]


def run_label(row: dict) -> str:
    return format_source_title(
        row.get("title") or "tracks",
        infer_source_kind(
            source_kind=row.get("source_kind"),
            source_fingerprint=row.get("source_fingerprint"),
        ),
    )


def _go(page_name: str) -> None:
    st.session_state["_nav_loading"] = True
    st.switch_page(str(Path(__file__).with_name(page_name)))


def open_new_separation() -> None:
    """Land on Isolate's upload form, not the last open mix."""
    open_home_shell(st.session_state)
    _go("isolate.py")


def open_saved_run(run_dir: str) -> None:
    """Open one local separation in the Isolate mixer."""
    st.session_state.pop(ISOLATE_SKIP_REHYDRATE_KEY, None)
    st.session_state["isolate_run_dir"] = run_dir
    st.session_state["isolate_viewing_run_dir"] = run_dir
    st.session_state[LISTEN_PICKER_NEXT_KEY] = run_dir
    st.session_state.pop("isolate_listen_applied_dir", None)
    add_open_mix_tab(st.session_state, run_dir)
    open_mix_shell(st.session_state)
    st.session_state[SHELL_TAB_KEY] = run_dir
    _go("isolate.py")


def _matches(row: dict, query: str) -> bool:
    needle = query.strip().casefold()
    if not needle:
        return True
    hay = f"{run_label(row)} {row.get('title') or ''}".casefold()
    return needle in hay


def main() -> None:
    st.html(_HOME_CSS)
    product = edition_product_name()
    st.title(product, anchor=False)
    st.caption("Separate a song, save audio, or sketch a tab. Everything stays on this computer.")

    owner = load_persist_isolate_user_id(st.session_state, DATA_DIR / ISOLATE_USER_ID_FILENAME)
    rows = library_rows(owner if isinstance(owner, str) else None)

    with st.container(key="att_home"):
        separate, youtube, tab_pdf = st.columns(3)
        with separate:
            if st.button(
                "Separate tracks",
                key="home_open_isolate",
                width="stretch",
                help="Split a song into stems and mix them",
            ):
                open_new_separation()
            st.caption("Vocals, drums, bass, guitar, and a mixer.")
        with youtube:
            if st.button(
                "Save from YouTube",
                key="home_open_youtube",
                width="stretch",
                help="Download a public video's audio to a folder. Does not separate stems.",
            ):
                _go("youtube_audio.py")
            st.caption("MP3 or another format, saved to a folder you pick.")
        with tab_pdf:
            if st.button(
                "Tab PDF",
                key="home_open_tab",
                width="stretch",
                help="Demo transcription. Tabs are rough drafts.",
            ):
                _go("tab_pdf.py")
            st.caption("A rough guitar tab from audio. Demo only.")

        st.subheader("Recents")
        if not rows:
            st.info("No separations yet. Separate a song to see it here.")
            if st.button("Separate a song", key="home_empty_separate"):
                open_new_separation()
        else:
            recent = rows[:6]
            cols = st.columns(len(recent))
            for index, row in enumerate(recent):
                run_dir = str(row.get("run_dir") or "")
                age = relative_age(row.get("created_at"))
                with cols[index]:
                    if st.button(
                        run_label(row),
                        key=f"home_recent_{index}",
                        width="stretch",
                        help=age or "Open this mix",
                    ):
                        open_saved_run(run_dir)
                    if age:
                        st.caption(age)

        st.subheader("Library")
        query = st.text_input(
            "Search library",
            key="home_library_query",
            placeholder="Search by name",
            label_visibility="collapsed",
        )
        shown = [row for row in rows if _matches(row, str(query or ""))]
        if rows and not shown:
            st.caption("Nothing in the library matches that search.")
        elif not rows:
            st.caption("Finished separations show up here.")
        else:
            for index, row in enumerate(shown):
                run_dir = str(row.get("run_dir") or "")
                age = relative_age(row.get("created_at"))
                label = run_label(row)
                if age:
                    label = f"{label}  ·  {age}"
                if st.button(label, key=f"home_file_{index}", width="stretch"):
                    open_saved_run(run_dir)


if __name__ == "__main__":
    main()
