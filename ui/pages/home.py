"""Desktop boot screen: launch the real jobs and reopen local separations."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from pathlib import Path

import streamlit as st

from ui.common import DATA_DIR, edition_product_name, list_recent_runs
from ui.design_tokens import ui_v2_enabled
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


def analysis_summary(row: dict) -> dict | None:
    """Compact analysis summary from meta.json, or from analysis.json on old runs."""
    summary = row.get("analysis")
    if isinstance(summary, dict) and summary:
        return summary
    artifacts = row.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    raw_path = artifacts.get("analysis")
    if not raw_path:
        return None
    path = Path(str(raw_path))
    if not path.is_file():
        return None
    try:
        from audio_to_tab.analysis import load_analysis

        result = load_analysis(path)
    except Exception:
        return None
    if result is None:
        return None
    return {
        "bpm": result.bpm,
        "key": result.key,
        "chord_count": len(result.chords),
        "section_count": len(result.sections),
    }


def analysis_line(summary: dict | None) -> str:
    """Small Home row line: BPM · Key · Sections."""
    if not summary:
        return "Not analysed yet"
    bpm_text = "BPM —"
    try:
        bpm = float(summary.get("bpm"))
    except (TypeError, ValueError):
        bpm = 0.0
    if bpm > 0:
        bpm_text = f"BPM {bpm:.0f}" if abs(bpm - round(bpm)) < 0.05 else f"BPM {bpm:.1f}"
    key_text = str(summary.get("key") or "Key —")
    raw_sections = summary.get("section_count")
    try:
        sections = int(raw_sections)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        sections = 0
    section_text = "1 section" if sections == 1 else f"{sections} sections"
    if sections <= 0:
        section_text = "No sections"
    return f"{bpm_text} · {key_text} · {section_text}"


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


def open_practice_run(run_dir: str) -> None:
    """Open a run in the mixer; the practice panel is part of that view."""
    open_saved_run(run_dir)


def _flash(message: str, *, error: bool = False) -> None:
    st.session_state["home_flash"] = (str(message), bool(error))


_TOKEN_MAP: dict[str, str] = {}

_HOME_CARDS: tuple[dict[str, object], ...] = (
    {
        "id": "learn",
        "title": "Learn a song",
        "subtitle": "Stems, chords, sections, tab, and loops.",
        "primary": True,
    },
    {
        "id": "youtube",
        "title": "Save from YouTube",
        "subtitle": "Save audio to a folder you pick.",
        "primary": False,
    },
    {
        "id": "tab",
        "title": "Tab PDF",
        "subtitle": "A rough guitar tab from audio.",
        "primary": False,
    },
)


def build_home_props(
    rows: list[dict],
    *,
    product: str = "Audio Tools",
    nonce: str | None = None,
    flash: tuple[str, bool] | None = None,
    loading: bool = False,
) -> dict:
    """Browser payload. Paths stay in ``_TOKEN_MAP`` and never in the dict."""
    _TOKEN_MAP.clear()
    issued = nonce or secrets.token_hex(8)
    public_rows: list[dict[str, str]] = []
    for row in rows:
        run_dir = str(row.get("run_dir") or "")
        summary = analysis_summary(row)
        token = ""
        if run_dir:
            token = hashlib.sha256(f"{issued}\n{run_dir}".encode()).hexdigest()[:16]
            _TOKEN_MAP[token] = run_dir
        public_rows.append(
            {
                "token": token,
                "title": run_label(row),
                "subtitle": analysis_line(summary),
                "age": relative_age(row.get("created_at")),
                "action": "practice" if summary else "analyse",
            }
        )
    flash_payload = None
    if isinstance(flash, tuple) and len(flash) == 2:
        flash_payload = {"message": str(flash[0]), "error": bool(flash[1])}
    return {
        "nonce": issued,
        "product": product,
        "cards": [dict(card) for card in _HOME_CARDS],
        "recents": public_rows[:6],
        "rows": public_rows,
        "loading": bool(loading),
        "flash": flash_payload,
    }


def _lockup_html() -> str:
    icon = Path(__file__).resolve().parents[1] / "icon.png"
    image = ""
    if icon.is_file():
        encoded = base64.b64encode(icon.read_bytes()).decode("ascii")
        image = f'<img alt="" src="data:image/png;base64,{encoded}"/>'
    return (
        '<div class="att-home-lockup" role="img" aria-label="Audio Tools">'
        f'<span class="mark">{image}</span><span class="word">Audio Tools</span></div>'
    )


def _handle_home_event(event: dict, tokens: dict[str, str]) -> None:
    kind = str(event.get("type") or "")
    ident = str(event.get("id") or "")
    if kind == "open_card":
        if ident == "learn":
            open_new_separation()
        elif ident == "youtube":
            _go("youtube_audio.py")
        elif ident == "tab":
            _go("tab_pdf.py")
        return
    run_dir = tokens.get(ident)
    if not run_dir:
        return
    if kind in {"open_recent", "open_row"}:
        open_saved_run(run_dir)
    elif kind == "practice":
        open_practice_run(run_dir)
    elif kind == "analyse":
        st.session_state["home_v2_pending"] = run_dir
        st.rerun()


def _main_v2() -> None:
    st.html('<div class="att-home-v2" hidden></div>')
    with st.sidebar:
        st.html(_lockup_html())
    stored_nonce = st.session_state.get("home_v2_nonce")
    stored_tokens = dict(st.session_state.get("home_v2_tokens") or {})
    owner = load_persist_isolate_user_id(st.session_state, DATA_DIR / ISOLATE_USER_ID_FILENAME)
    rows = library_rows(owner if isinstance(owner, str) else None)
    pending = st.session_state.get("home_v2_pending")
    show_loading = bool(pending) and not st.session_state.get("home_v2_pending_shown")
    flash = None
    if not show_loading:
        raw_flash = st.session_state.pop("home_flash", None)
        if isinstance(raw_flash, tuple) and len(raw_flash) == 2:
            flash = (str(raw_flash[0]), bool(raw_flash[1]))
    props = build_home_props(
        rows,
        product=edition_product_name(),
        flash=flash,
        loading=show_loading,
    )
    st.session_state["home_v2_nonce"] = props["nonce"]
    st.session_state["home_v2_tokens"] = dict(_TOKEN_MAP)
    try:
        from ui.home_component import home_build_is_complete, home_library
    except Exception:
        _main_legacy()
        return
    if not home_build_is_complete():
        _main_legacy()
        return
    try:
        event = home_library(props, key="home_v2")
    except Exception:
        _main_legacy()
        return
    if show_loading:
        st.session_state["home_v2_pending_shown"] = True
        st.rerun()
    if isinstance(event, dict) and event.get("nonce") == stored_nonce:
        _handle_home_event(event, stored_tokens)
    if pending and st.session_state.get("home_v2_pending_shown"):
        st.session_state.pop("home_v2_pending", None)
        st.session_state.pop("home_v2_pending_shown", None)
        from ui.isolate_jobs import analyse_existing_run

        ok, message = analyse_existing_run(str(pending))
        _flash(
            message,
            error=not ok or str(message).startswith("Analysis ready with warnings"),
        )
        st.rerun()


def _matches(row: dict, query: str) -> bool:
    needle = query.strip().casefold()
    if not needle:
        return True
    hay = f"{run_label(row)} {row.get('title') or ''}".casefold()
    return needle in hay


def _main_legacy() -> None:
    st.html(_HOME_CSS)
    product = edition_product_name()
    st.title(product, anchor=False)
    st.caption("Separate a song, save audio, or sketch a tab. Everything stays on this computer.")
    flash = st.session_state.pop("home_flash", None)
    if isinstance(flash, tuple) and len(flash) == 2:
        message, is_error = flash
        if is_error:
            st.warning(str(message))
        else:
            st.success(str(message))

    owner = load_persist_isolate_user_id(st.session_state, DATA_DIR / ISOLATE_USER_ID_FILENAME)
    rows = library_rows(owner if isinstance(owner, str) else None)

    with st.container(key="att_home"):
        separate, youtube, tab_pdf = st.columns(3)
        with separate:
            if st.button(
                "Learn a song",
                key="home_open_isolate",
                width="stretch",
                help="Separate a song, then practise with chords, sections, tab, and loops",
            ):
                open_new_separation()
            st.caption("Stems, chords, sections, tab, and slow-practice loops.")
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
                summary = analysis_summary(row)
                open_col, action_col = st.columns([6, 1], gap="small")
                with open_col:
                    if st.button(label, key=f"home_file_{index}", width="stretch"):
                        open_saved_run(run_dir)
                    st.caption(analysis_line(summary))
                with action_col:
                    if summary:
                        if st.button(
                            "Practice",
                            key=f"home_practice_{index}",
                            width="stretch",
                            help="Open the mixer with chords, sections, lyrics, and tab.",
                        ):
                            open_practice_run(run_dir)
                    else:
                        if st.button(
                            "Analyse",
                            key=f"home_analyse_{index}",
                            width="stretch",
                            help="Build chords, sections, lyrics, key, and BPM for this run.",
                        ):
                            from ui.isolate_jobs import analyse_existing_run

                            with st.spinner("Analysing song…"):
                                ok, message = analyse_existing_run(run_dir)
                            _flash(
                                message,
                                error=not ok
                                or message.startswith("Analysis ready with warnings"),
                            )
                            st.rerun()


def main() -> None:
    if ui_v2_enabled():
        _main_v2()
        return
    _main_legacy()


if __name__ == "__main__":
    main()
