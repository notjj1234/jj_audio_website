"""Streamlit page: YouTube Audio — download a public video’s audio to a folder."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ui.common import delete_run, ensure_src_path, run_output_dir
from ui.desktop_export import (
    EXPORT_FORMAT_LABELS,
    EXPORT_FORMATS,
    choose_export_dir,
    export_mix_to_folder,
    open_path_in_os,
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
YT_AUDIO_PICKER_NOTE_KEY = "yt_audio_picker_note"
YT_AUDIO_ERROR_KEY = "yt_audio_error"
YT_AUDIO_SUCCESS_KEY = "yt_audio_success"
YT_AUDIO_DOWNLOADING_KEY = "yt_audio_downloading"

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
        search_q = st.text_input(
            "Song or artist",
            key=YT_AUDIO_SEARCH_QUERY_KEY,
            placeholder="e.g. artist, song title",
        )
        do_search = st.form_submit_button("Search", width="stretch")
    action_cols = st.columns([1, 1])
    with action_cols[0]:
        if st.button("Clear results", key="yt_audio_search_clear", width="stretch"):
            st.session_state.pop(YT_AUDIO_SEARCH_HITS_KEY, None)
            st.session_state.pop(YT_AUDIO_SEARCH_ERROR_KEY, None)
            st.rerun()
    with action_cols[1]:
        if st.button("Close", key="yt_audio_search_close", width="stretch"):
            _close_search_dialog()
            st.rerun()
    if do_search:
        try:
            with st.spinner("Searching YouTube…"):
                hits = search_youtube_videos(search_q, max_results=5)
            st.session_state[YT_AUDIO_SEARCH_HITS_KEY] = [
                {
                    "video_id": h.video_id,
                    "title": h.title,
                    "channel": h.channel,
                    "duration_sec": h.duration_sec,
                    "url": h.url,
                    "thumbnail_url": h.thumbnail_url,
                }
                for h in hits
            ]
            st.session_state.pop(YT_AUDIO_SEARCH_ERROR_KEY, None)
            if not hits:
                st.session_state[YT_AUDIO_SEARCH_ERROR_KEY] = (
                    "No public videos matched that search."
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
    search_error = st.session_state.get(YT_AUDIO_SEARCH_ERROR_KEY)
    if search_error:
        st.warning(str(search_error))
    hits_state = st.session_state.get(YT_AUDIO_SEARCH_HITS_KEY) or []
    if isinstance(hits_state, list) and hits_state:
        st.caption(f"{len(hits_state)} result(s)")
        for hit in hits_state:
            if not isinstance(hit, dict):
                continue
            vid = str(hit.get("video_id") or "")
            title = str(hit.get("title") or "Untitled")
            channel = str(hit.get("channel") or "")
            dur = format_youtube_duration(hit.get("duration_sec"))
            url = str(hit.get("url") or "").strip()
            thumb = str(hit.get("thumbnail_url") or "").strip()
            meta_bits = [b for b in (channel, dur) if b]
            meta = " · ".join(meta_bits)
            row = st.columns([1, 3, 1], vertical_alignment="center")
            with row[0]:
                if thumb:
                    st.image(thumb, width=120)
            with row[1]:
                st.markdown(f"**{title}**")
                if meta:
                    st.caption(meta)
            with row[2]:
                if st.button(
                    "Use",
                    key=f"yt_audio_pick_{vid}",
                    disabled=not url,
                    width="stretch",
                    help="Fill the YouTube URL so you can save audio to a folder.",
                ):
                    _queue_url(url)
                    st.session_state.pop(YT_AUDIO_SEARCH_ERROR_KEY, None)
                    _close_search_dialog()
                    st.rerun()
            with st.expander(
                "Preview",
                expanded=False,
                key=f"yt_audio_preview_{vid}",
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
    st.title(
        "YouTube Audio",
        anchor=False,
        help=(
            "Download audio from a public YouTube link and save it to a folder. "
            "This page does not separate stems — use Audio Isolation for that."
        ),
    )
    st.caption(
        "Paste or search a public YouTube link, pick a format, then choose a folder. "
        "Save only — no stem separation. Processing stays on this computer."
    )
    st.caption(
        "The sidebar Interface Lite/Pro setting does not apply on this page."
    )
    st.caption(
        "If the folder window is hidden, Alt+Tab. Saving overwrites a same-named file. "
        "On Linux, a missing zenity picker is treated as cancel."
    )
    st.caption(YOUTUBE_DISCLAIMER)

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
            "Search songs",
            key="yt_audio_search_open_btn",
            width="stretch",
            help="Open a search panel to find a public video by song or artist.",
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

    st.selectbox(
        "Audio format",
        options=list(EXPORT_FORMATS),
        format_func=lambda f: EXPORT_FORMAT_LABELS.get(f, f),
        key=YT_AUDIO_FMT_KEY,
        help="WAV is the downloaded original. Other formats are converted with ffmpeg.",
    )
    fmt = str(st.session_state.get(YT_AUDIO_FMT_KEY) or _DEFAULT_FMT)
    if fmt not in EXPORT_FORMATS:
        fmt = _DEFAULT_FMT

    busy = bool(st.session_state.get(YT_AUDIO_DOWNLOADING_KEY))
    save_clicked = st.button(
        "Save audio to folder",
        type="primary",
        disabled=not url_ok or busy,
        help="Download if needed, then choose a folder in Explorer or Finder.",
    )
    if save_clicked:
        if not url:
            st.session_state[YT_AUDIO_ERROR_KEY] = "Paste a YouTube URL."
        elif not url_ok:
            st.session_state[YT_AUDIO_ERROR_KEY] = "Only YouTube URLs are allowed."
        else:
            _run_save_flow(url, fmt, already_staged=staged)
            st.rerun()

    if staged is not None and not save_clicked:
        if st.button(
            "Choose folder",
            key="yt_audio_choose_folder",
            help="Audio is already downloaded. Pick a folder to save it.",
        ):
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


if __name__ == "__main__":
    main()
