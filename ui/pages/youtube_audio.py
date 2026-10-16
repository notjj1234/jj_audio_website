"""Streamlit page: YouTube to MP3 — download a public video’s audio to a folder."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ui.common import delete_run, ensure_src_path, run_output_dir
from ui.desktop_export import (
    EXPORT_FORMAT_LABELS,
    EXPORT_FORMAT_PLAIN_LABELS,
    EXPORT_FORMATS,
    choose_export_dir,
    export_mix_to_folder,
    open_path_in_os,
)
from ui.isolate_state import is_pro_mode
from ui.youtube_search import (
    PAGE_SIZE as YT_SEARCH_PAGE_SIZE,
    has_next_page,
    hits_as_dicts,
    meta_line,
    normalize_page,
    page_offset,
    result_range_caption,
)

ensure_src_path()

from audio_to_tab.ingest import (  # noqa: E402
    YouTubeDownloadError,
    YouTubeSearchError,
    download_youtube_audio,
    format_youtube_duration,
    is_youtube_url,
    search_youtube_videos,
)
from audio_to_tab.pipeline import YOUTUBE_DISCLAIMER  # noqa: E402

YT_AUDIO_URL_KEY = "yt_audio_url"
YT_AUDIO_URL_PENDING_KEY = "yt_audio_url_pending"
YT_AUDIO_FMT_KEY = "yt_audio_fmt"
YT_AUDIO_WAV_KEY = "yt_audio_wav"
YT_AUDIO_WORK_DIR_KEY = "yt_audio_work_dir"
YT_AUDIO_STAGED_URL_KEY = "yt_audio_staged_url"
YT_AUDIO_LAST_PATH_KEY = "yt_audio_last_path"
YT_AUDIO_REVEALED_KEY = "yt_audio_revealed_path"
YT_AUDIO_SEARCH_OPEN_KEY = "yt_audio_search_open"
YT_AUDIO_SEARCH_HITS_KEY = "yt_audio_search_hits"
YT_AUDIO_SEARCH_ERROR_KEY = "yt_audio_search_error"
YT_AUDIO_SEARCH_QUERY_KEY = "yt_audio_search_query"
YT_AUDIO_SEARCH_PAGE_KEY = "yt_audio_search_page"
YT_AUDIO_PICKER_NOTE_KEY = "yt_audio_picker_note"
YT_AUDIO_ERROR_KEY = "yt_audio_error"
YT_AUDIO_SUCCESS_KEY = "yt_audio_success"
YT_AUDIO_DOWNLOADING_KEY = "yt_audio_downloading"
YT_AUDIO_FLASH_KEY = "yt_audio_flash"

_DEFAULT_FMT = "mp3"
_PICKER_CANCEL_COPY = "Folder picker was cancelled or is not available."


def save_youtube_audio_to_folder(
    url: str,
    dest_dir: Path,
    fmt: str,
    *,
    work_dir: Path,
    wav_path: Path | None = None,
    download_fn=download_youtube_audio,
    export_fn=export_mix_to_folder,
) -> Path:
    """Download public YouTube audio if needed, then convert into ``dest_dir``.

    Does not delete ``work_dir``. Callers clean staging after a successful save.
    """
    cleaned = (url or "").strip()
    if not is_youtube_url(cleaned):
        raise ValueError("Only YouTube URLs are allowed")
    wav = Path(wav_path) if wav_path is not None else None
    if wav is None or not wav.is_file():
        wav = Path(download_fn(cleaned, work_dir))
    return Path(export_fn(wav, dest_dir, wav.name, fmt))


def _apply_pending_url() -> None:
    if YT_AUDIO_URL_PENDING_KEY not in st.session_state:
        return
    pending = st.session_state.pop(YT_AUDIO_URL_PENDING_KEY)
    st.session_state[YT_AUDIO_URL_KEY] = str(pending or "")


def _queue_url(url: str) -> None:
    st.session_state[YT_AUDIO_URL_PENDING_KEY] = (url or "").strip()


def _discard_staging() -> None:
    work = st.session_state.get(YT_AUDIO_WORK_DIR_KEY)
    if work:
        delete_run(work)
    st.session_state.pop(YT_AUDIO_WAV_KEY, None)
    st.session_state.pop(YT_AUDIO_WORK_DIR_KEY, None)
    st.session_state.pop(YT_AUDIO_STAGED_URL_KEY, None)


def _staged_wav_for(url: str) -> Path | None:
    staged_url = str(st.session_state.get(YT_AUDIO_STAGED_URL_KEY) or "")
    raw = st.session_state.get(YT_AUDIO_WAV_KEY)
    if not raw or staged_url != url:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def _close_search_dialog() -> None:
    st.session_state[YT_AUDIO_SEARCH_OPEN_KEY] = False


def _clear_search_results() -> None:
    st.session_state.pop(YT_AUDIO_SEARCH_HITS_KEY, None)
    st.session_state.pop(YT_AUDIO_SEARCH_ERROR_KEY, None)
    st.session_state[YT_AUDIO_SEARCH_PAGE_KEY] = 1


def _run_search(query: str, *, page: int) -> None:
    page = normalize_page(page)
    st.session_state[YT_AUDIO_SEARCH_PAGE_KEY] = page
    try:
        with st.spinner("Searching YouTube…"):
            hits = search_youtube_videos(
                query,
                max_results=YT_SEARCH_PAGE_SIZE,
                offset=page_offset(page),
            )
        st.session_state[YT_AUDIO_SEARCH_HITS_KEY] = hits_as_dicts(hits)
        st.session_state.pop(YT_AUDIO_SEARCH_ERROR_KEY, None)
        if not hits:
            st.session_state[YT_AUDIO_SEARCH_ERROR_KEY] = (
                "No public videos matched that search."
                if page <= 1
                else "No more public videos for this search."
            )
    except ValueError as exc:
        st.session_state[YT_AUDIO_SEARCH_HITS_KEY] = []
        st.session_state[YT_AUDIO_SEARCH_ERROR_KEY] = str(exc)
    except YouTubeSearchError as exc:
        st.session_state[YT_AUDIO_SEARCH_HITS_KEY] = []
        st.session_state[YT_AUDIO_SEARCH_ERROR_KEY] = str(exc)
    except Exception as exc:
        st.session_state[YT_AUDIO_SEARCH_HITS_KEY] = []
        st.session_state[YT_AUDIO_SEARCH_ERROR_KEY] = f"YouTube search failed: {exc}"


def _download_wav(url: str, *, title: str) -> tuple[Path | None, str | None]:
    """Download into a new staging dir. Returns (path, error)."""
    prev_work = st.session_state.get(YT_AUDIO_WORK_DIR_KEY)
    work_dir = run_output_dir()
    st.session_state[YT_AUDIO_DOWNLOADING_KEY] = title
    try:
        path = download_youtube_audio(url, work_dir)
        if prev_work and str(prev_work) != str(work_dir):
            delete_run(prev_work)
        st.session_state[YT_AUDIO_WAV_KEY] = str(path)
        st.session_state[YT_AUDIO_WORK_DIR_KEY] = str(work_dir)
        st.session_state[YT_AUDIO_STAGED_URL_KEY] = url
        return path, None
    except YouTubeDownloadError as exc:
        delete_run(work_dir)
        return None, str(exc)
    except Exception as exc:
        delete_run(work_dir)
        return None, f"YouTube download failed: {exc}"
    finally:
        st.session_state.pop(YT_AUDIO_DOWNLOADING_KEY, None)


def _export_staged(url: str, dest_dir: Path, fmt: str, wav: Path) -> Path:
    work_raw = st.session_state.get(YT_AUDIO_WORK_DIR_KEY)
    work_dir = Path(work_raw) if work_raw else wav.parent
    return save_youtube_audio_to_folder(
        url,
        dest_dir,
        fmt,
        work_dir=work_dir,
        wav_path=wav,
    )


@st.dialog("Search YouTube", width="large", on_dismiss=_close_search_dialog)
def _youtube_search_dialog() -> None:
    """Centered modal: search public videos and fill the URL field."""
    st.caption(
        "Find a public video and click **Use**. Then pick a format and save it "
        "to a folder."
    )
    with st.form("yt_audio_search_form", clear_on_submit=False, border=False):
        search_cols = st.columns([4, 1], vertical_alignment="bottom")
        with search_cols[0]:
            search_q = st.text_input(
                "Song or artist",
                key=YT_AUDIO_SEARCH_QUERY_KEY,
                placeholder="e.g. artist, song title",
            )
        with search_cols[1]:
            do_search = st.form_submit_button(
                "Search",
                type="primary",
                width="stretch",
            )
    secondary = st.columns([1, 1, 4], vertical_alignment="center")
    with secondary[0]:
        if st.button(
            "Clear",
            key="yt_audio_search_clear",
            type="secondary",
            width="stretch",
        ):
            _clear_search_results()
            st.rerun()
    with secondary[1]:
        if st.button(
            "Close",
            key="yt_audio_search_close",
            type="secondary",
            width="stretch",
        ):
            _close_search_dialog()
            st.rerun()
    if do_search:
        _run_search(search_q, page=1)
    search_error = st.session_state.get(YT_AUDIO_SEARCH_ERROR_KEY)
    if search_error:
        st.warning(str(search_error))
    downloading_title = st.session_state.get(YT_AUDIO_DOWNLOADING_KEY)
    if downloading_title:
        st.info(f"Downloading **{downloading_title}**…")
    page = normalize_page(st.session_state.get(YT_AUDIO_SEARCH_PAGE_KEY, 1))
    hits_state = st.session_state.get(YT_AUDIO_SEARCH_HITS_KEY) or []
    if not isinstance(hits_state, list):
        hits_state = []
    busy = bool(downloading_title)
    if hits_state:
        st.caption(result_range_caption(page, len(hits_state)))
        for hit in hits_state:
            if not isinstance(hit, dict):
                continue
            vid = str(hit.get("video_id") or "")
            title = str(hit.get("title") or "Untitled")
            dur = format_youtube_duration(hit.get("duration_sec"))
            url = str(hit.get("url") or "").strip()
            thumb = str(hit.get("thumbnail_url") or "").strip()
            meta = meta_line(hit, duration_label=dur)
            row = st.columns([1.5, 3.2, 1.3], vertical_alignment="center")
            with row[0]:
                if thumb:
                    st.image(thumb, width=168)
            with row[1]:
                st.markdown(f"**{title}**")
                if meta:
                    st.caption(meta)
            with row[2]:
                if st.button(
                    "Use",
                    key=f"yt_audio_pick_p{page}_{vid}",
                    type="primary",
                    disabled=not url or busy,
                    width="stretch",
                    help="Download this track and prepare to save it to a folder.",
                ):
                    _queue_url(url)
                    st.session_state.pop(YT_AUDIO_SEARCH_ERROR_KEY, None)
                    # Download to staging so main page can save directly
                    with st.status(f'Downloading "{title}"…', expanded=True) as status:
                        st.write("Fetching audio from YouTube. This can take a minute.")
                        path, err = _download_wav(url, title=title)
                        if err:
                            status.update(label="Download failed", state="error")
                            st.session_state[YT_AUDIO_SEARCH_ERROR_KEY] = err
                        else:
                            status.update(
                                label=f"Ready: {Path(path).stem}",
                                state="complete",
                            )
                            st.session_state[YT_AUDIO_FLASH_KEY] = (
                                f"Downloaded **{title}**. Click **Save to folder**."
                            )
                    _close_search_dialog()
                    st.rerun()
            with st.expander(
                "Preview",
                expanded=False,
                key=f"yt_audio_preview_p{page}_{vid}",
            ):
                if url:
                    if thumb:
                        st.image(thumb, use_container_width=True)
                    st.caption(
                        "In-app YouTube playback is often blocked for official music "
                        "uploads. Open the video on YouTube, or click **Use** to fill "
                        "the URL."
                    )
                    st.markdown(f"[Open on YouTube]({url})")
                else:
                    st.caption("No preview URL for this result.")
    if hits_state or page > 1:
        nav = st.columns([1, 2, 1], vertical_alignment="center")
        with nav[0]:
            if st.button(
                "Previous",
                key="yt_audio_search_prev",
                type="secondary",
                disabled=page <= 1 or busy,
                width="stretch",
            ):
                _run_search(
                    str(st.session_state.get(YT_AUDIO_SEARCH_QUERY_KEY) or ""),
                    page=page - 1,
                )
                st.rerun()
        with nav[1]:
            st.caption(result_range_caption(page, len(hits_state)))
        with nav[2]:
            if st.button(
                "Next",
                key="yt_audio_search_next",
                type="secondary",
                disabled=not has_next_page(len(hits_state)) or busy,
                width="stretch",
            ):
                _run_search(
                    str(st.session_state.get(YT_AUDIO_SEARCH_QUERY_KEY) or ""),
                    page=page + 1,
                )
                st.rerun()

def _run_save_flow(url: str, fmt: str, *, already_staged: Path | None) -> None:
    """Download if needed, then native folder picker, then convert."""
    st.session_state.pop(YT_AUDIO_PICKER_NOTE_KEY, None)
    st.session_state.pop(YT_AUDIO_ERROR_KEY, None)
    st.session_state.pop(YT_AUDIO_SUCCESS_KEY, None)

    wav = already_staged
    if wav is None:
        title = Path(url.rstrip("/")).name or "YouTube audio"
        with st.status("Downloading audio from YouTube…", expanded=True) as status:
            st.write("Fetching audio from YouTube. This can take a minute.")
            path, err = _download_wav(url, title=title)
            if err:
                status.update(label="Download failed", state="error")
                st.session_state[YT_AUDIO_ERROR_KEY] = err
                return
            wav = path
            ready_name = Path(path).stem if path else title
            status.update(label=f"Ready: {ready_name}", state="complete")
    if wav is None:
        st.session_state[YT_AUDIO_ERROR_KEY] = "YouTube download failed."
        return

    picked = choose_export_dir()
    if picked is None:
        st.session_state[YT_AUDIO_PICKER_NOTE_KEY] = _PICKER_CANCEL_COPY
        return

    dest_name = f"{wav.stem}.{fmt}"
    try:
        with st.spinner(f"Saving {dest_name}…"):
            saved = _export_staged(url, picked, fmt, wav)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        st.session_state[YT_AUDIO_ERROR_KEY] = str(exc)
        return
    except Exception as exc:
        st.session_state[YT_AUDIO_ERROR_KEY] = str(exc)
        return

    _discard_staging()
    st.session_state[YT_AUDIO_LAST_PATH_KEY] = str(saved)
    st.session_state[YT_AUDIO_SUCCESS_KEY] = f"Saved {saved.name} to {saved.parent}"
    if st.session_state.get(YT_AUDIO_REVEALED_KEY) != str(saved):
        open_path_in_os(saved)
        st.session_state[YT_AUDIO_REVEALED_KEY] = str(saved)


def main() -> None:
    pro = is_pro_mode(st.session_state)
    title_help = (
        "Download audio from a public YouTube link and save it to a folder "
        "(MP3 by default; WAV/FLAC/etc. also available). "
        "This page does not separate stems — use Audio Isolation for that. "
        "If the folder window is hidden, Alt+Tab. Saving overwrites a same-named file."
    ) if pro else None
    st.title(
        "YouTube to MP3",
        anchor=False,
        help=title_help,
    )
    st.caption(YOUTUBE_DISCLAIMER)
    # Always visible (Lite has no title help) — product boundary + picker friction.
    st.caption(
        "Saves audio to a folder only — it does not separate stems "
        "(use **Audio Isolation** for that). "
        "If the folder window is hidden, Alt+Tab. "
        "Saving overwrites a same-named file."
    )

    _apply_pending_url()
    if YT_AUDIO_FMT_KEY not in st.session_state:
        st.session_state[YT_AUDIO_FMT_KEY] = _DEFAULT_FMT

    url_row = st.columns([4, 1], vertical_alignment="bottom")
    with url_row[0]:
        youtube_url = st.text_input(
            "YouTube URL",
            key=YT_AUDIO_URL_KEY,
            placeholder="https://www.youtube.com/watch?v=…",
        )
    with url_row[1]:
        if st.button(
            "Search",
            key="yt_audio_search_open_btn",
            type="secondary",
            width="stretch",
            help="Open a search panel to find a public video by song or artist." if pro else None,
        ):
            st.session_state[YT_AUDIO_SEARCH_OPEN_KEY] = True
            st.rerun()
    if st.session_state.get(YT_AUDIO_SEARCH_OPEN_KEY):
        _youtube_search_dialog()

    url = (youtube_url or "").strip()
    url_ok = bool(url) and is_youtube_url(url)
    if url and not url_ok:
        st.error("Only YouTube URLs are allowed.")

    staged_url = st.session_state.get(YT_AUDIO_STAGED_URL_KEY)
    if staged_url and staged_url != url:
        _discard_staging()
    staged = _staged_wav_for(url) if url_ok else None

    labels = EXPORT_FORMAT_LABELS if pro else EXPORT_FORMAT_PLAIN_LABELS
    fmt_help = (
        "WAV is the downloaded original. Other formats are converted with ffmpeg."
        if pro
        else None
    )
    st.selectbox(
        "Audio format",
        options=list(EXPORT_FORMATS),
        format_func=lambda f: labels.get(f, f),
        key=YT_AUDIO_FMT_KEY,
        help=fmt_help,
    )
    fmt = str(st.session_state.get(YT_AUDIO_FMT_KEY) or _DEFAULT_FMT)
    if fmt not in EXPORT_FORMATS:
        fmt = _DEFAULT_FMT

    busy = bool(st.session_state.get(YT_AUDIO_DOWNLOADING_KEY))
    save_clicked = st.button(
        "Save to folder",
        type="primary",
        disabled=not url_ok or busy,
        help="Download if needed, then choose a folder in Explorer or Finder." if pro else None,
    )
    if save_clicked:
        if not url:
            st.session_state[YT_AUDIO_ERROR_KEY] = "Paste a YouTube URL."
        elif not url_ok:
            st.session_state[YT_AUDIO_ERROR_KEY] = "Only YouTube URLs are allowed."
        else:
            _run_save_flow(url, fmt, already_staged=staged)
            st.rerun()

    if note := st.session_state.get(YT_AUDIO_PICKER_NOTE_KEY):
        st.caption(str(note))
    if err := st.session_state.get(YT_AUDIO_ERROR_KEY):
        st.error(str(err))
    if flash := st.session_state.get(YT_AUDIO_SUCCESS_KEY):
        st.success(str(flash))
        last = st.session_state.get(YT_AUDIO_LAST_PATH_KEY)
        if last:
            if st.button("Show in folder", key="yt_audio_show_folder"):
                if not open_path_in_os(Path(last)):
                    st.caption("Could not open the folder.")
    if flash := st.session_state.pop(YT_AUDIO_FLASH_KEY, None):
        st.success(str(flash))


if __name__ == "__main__":
    main()
