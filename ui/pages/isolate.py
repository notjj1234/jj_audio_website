"""Streamlit page: Audio Isolation — separate songs into instrument tracks."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sys
import time
import uuid
from pathlib import Path

import streamlit as st

from ui.common import (
    AUDIO_UPLOAD_TYPES,
    DATA_DIR,
    ensure_src_path,
    list_recent_runs,
    rename_run_title,
    run_output_dir,
    save_upload,
)
from ui.desktop_export import (
    EXPORT_FORMAT_LABELS,
    EXPORT_FORMATS,
    choose_export_dir,
    default_export_dir,
    export_mix_to_folder,
    export_song_dir,
    export_tracks_to_folder,
    open_path_in_os,
)
from ui.desktop_notify import notify as desktop_notify
from ui.guitar_fixup import (
    GUITAR_BACKUP_NAME,
    GUITAR_PREREFINE_NAME,
    GUITAR_REFINED_NAME,
    apply_mixer_guitar_fixup,
    has_guitar_backup,
    has_guitar_prerefine,
    invalidate_mixer_playback,
    load_fold_other_diagnostics,
    load_guitar_stem_quality,
    merge_artifact_updates,
    reset_mixer_guitar_fixup,
    switch_mixer_guitar_variant,
)
from ui.isolate_jobs import (
    IsolateJobSpec,
    active_job_id,
    apply_succeeded_job_to_session,
    delete_all_finished_jobs,
    delete_finished_job,
    delete_library_run,
    enqueue_job,
    ensure_worker_started,
    format_job_error,
    jobs_visible_in_queue,
    list_jobs,
    merge_library_runs,
    pause_job,
    queued_job_ids,
    read_status,
    remove_job,
    resume_job,
    worker_busy,
)
from ui.isolate_state import (
    DEFAULT_SPEED_PRESET,
    DEFAULT_TRACK_OPTIONS,
    DEMUCS_STEM_CHECKBOX_IDS,
    GUITAR_TRACK_OPTION_IDS,
    ISOLATE_EXPORT_DIR_KEY,
    ISOLATE_UI_STATE_FILENAME,
    ISOLATE_USER_ID_FILENAME,
    LISTEN_PICKER_KEY,
    LISTEN_PICKER_NEXT_KEY,
    ROFORMER_BACKEND_UI_HINT,
    ROFORMER_SPEED_PRESET_NOTE,
    SPEED_PRESETS,
    TRACK_OPTIONS,
    VOCALS_INSTRUMENTAL_OPTION_ID,
    WORKSPACE_KEY,
    WORKSPACE_NEXT_KEY,
    WORKSPACE_TABS,
    apply_listen_picker_pending,
    apply_pending_output_name,
    apply_pending_youtube_url,
    apply_stored_isolate_ui_state,
    apply_workspace_tab,
    apply_youtube_output_name_sync,
    clamp_region_bounds,
    format_source_caption,
    format_source_title,
    guitar_track_radio_ids,
    infer_source_kind,
    is_stopping_previous_job,
    isolate_ui_state_payload,
    job_requires_roformer_backend,
    jobs_needing_os_notify,
    listen_picker_default,
    load_persist_isolate_user_id,
    migrate_track_options,
    normalize_guitar_track_selection,
    os_notify_message,
    partition_queue_jobs,
    paused_job_caption,
    pending_audio_needs_resave,
    pending_upload_fp_for_stale,
    plan_isolate_job_poll,
    promote_default_guitar_option,
    queue_reopen_output_name,
    queue_youtube_url,
    queued_wait_caption,
    read_isolate_ui_state,
    recent_runs_with_owner_fallback,
    reset_new_tab_source,
    resolve_speed_preset,
    resolve_track_selection,
    resolve_youtube_job_name,
    running_progress_view,
    select_rehydrate_row,
    session_mixer_artifacts_ok,
    should_hide_stale_results,
    staged_audio_for_new_tab,
    status_strip_waiting_caption,
    stem_label_for_id,
    sync_output_name_on_upload,
    tracks_picker_help,
    upload_fingerprint,
    write_isolate_ui_state,
)
from ui.media import (
    ensure_mixer_audio_paths,
    ensure_region_preview_wav,
    register_mixer_media,
    stem_media_urls,
)
from ui.stem_mixer_component import component_build_available, stem_mixer

ensure_src_path()

from audio_to_tab.hardware import (  # noqa: E402
    CUDA_UNAVAILABLE_MESSAGE,
    desktop_device_options,
    desktop_recommend_caption,
    desktop_system_summary,
    ensure_cuda_available,
    get_desktop_probe,
    get_desktop_probe_without_torch,
)
from audio_to_tab.ingest import (  # noqa: E402
    YouTubeDownloadError,
    YouTubeSearchError,
    download_youtube_audio,
    format_youtube_duration,
    is_youtube_url,
    search_youtube_videos,
)
from audio_to_tab.isolate import (  # noqa: E402
    DEMUCS_INSTALL_HINT,
    MIN_REGION_SEC,
    RegionError,
    format_region_label,
    format_region_label_filename,
    format_time_sec,
    probe_duration_sec,
    resolve_region,
)
from audio_to_tab.mixer import (  # noqa: E402
    DB_DEFAULT,
    effective_linear_gains,
    mix_stems_to_wav,
    sort_stem_names,
    stem_display_name,
    waveform_peaks,
)
from audio_to_tab.pipeline import YOUTUBE_DISCLAIMER  # noqa: E402
from audio_to_tab.roformer import (  # noqa: E402
    ROFORMER_INSTALL_HINT,
    is_roformer_backend_available,
)
from audio_to_tab.separate import is_demucs_available  # noqa: E402

logger = logging.getLogger(__name__)

STEM_HINTS = {
    "piano": "May sound less accurate than other tracks",
    "guitar": "Isolation is harder than vocals/drums/bass; Best guitar is slower but cleaner",
    "guitar1": "Legacy spatial label",
    "guitar2": "Legacy spatial label",
}

ISOLATE_YOUTUBE_SEARCH_OPEN_KEY = "isolate_youtube_search_open"


def _close_youtube_search_dialog() -> None:
    st.session_state[ISOLATE_YOUTUBE_SEARCH_OPEN_KEY] = False


@st.dialog("Search YouTube", width="large", on_dismiss=_close_youtube_search_dialog)
def _youtube_search_dialog() -> None:
    """Centered modal: search public videos, pick one to fill the URL field."""
    st.caption("Find a public video, then use Download audio on the New tab.")
    with st.form("isolate_youtube_search_form", clear_on_submit=False, border=False):
        search_q = st.text_input(
            "Song or artist",
            key="isolate_youtube_search_query",
            placeholder="e.g. artist — song title",
        )
        do_search = st.form_submit_button(
            "Search",
            width="stretch",
        )
    action_cols = st.columns([1, 1])
    with action_cols[0]:
        if st.button(
            "Clear results",
            key="isolate_youtube_search_clear",
            width="stretch",
        ):
            st.session_state.pop("isolate_youtube_search_hits", None)
            st.session_state.pop("isolate_youtube_search_error", None)
            st.rerun()
    with action_cols[1]:
        if st.button(
            "Close",
            key="isolate_youtube_search_close",
            width="stretch",
        ):
            _close_youtube_search_dialog()
            st.rerun()
    if do_search:
        try:
            with st.spinner("Searching YouTube…"):
                hits = search_youtube_videos(search_q, max_results=5)
            st.session_state["isolate_youtube_search_hits"] = [
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
            st.session_state.pop("isolate_youtube_search_error", None)
            if not hits:
                st.session_state["isolate_youtube_search_error"] = (
                    "No public videos matched that search."
                )
        except ValueError as exc:
            st.session_state["isolate_youtube_search_hits"] = []
            st.session_state["isolate_youtube_search_error"] = str(exc)
        except YouTubeSearchError as exc:
            st.session_state["isolate_youtube_search_hits"] = []
            st.session_state["isolate_youtube_search_error"] = str(exc)
        except Exception as exc:
            st.session_state["isolate_youtube_search_hits"] = []
            st.session_state["isolate_youtube_search_error"] = (
                f"YouTube search failed: {exc}"
            )
    search_error = st.session_state.get("isolate_youtube_search_error")
    if search_error:
        st.warning(str(search_error))
    hits_state = st.session_state.get("isolate_youtube_search_hits") or []
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
                    key=f"isolate_youtube_pick_{vid}",
                    disabled=not url,
                    width="stretch",
                ):
                    queue_youtube_url(st.session_state, url)
                    st.session_state.pop("isolate_youtube_search_error", None)
                    _close_youtube_search_dialog()
                    st.rerun()
            with st.expander(
                "Preview",
                expanded=False,
                key=f"isolate_youtube_preview_{vid}",
            ):
                if url:
                    st.video(url)
                    st.markdown(f"[Open on YouTube]({url})")
                else:
                    st.caption("No preview URL for this result.")


def _stateful_expander(label: str, *, key: str, default: bool = False):
    """
    Expander that remembers whether the user left it open.

    The live mixer reruns the page on every interaction. Without a key the
    expander would snap back to ``default`` each time; with one, Streamlit
    tracks the open state in ``st.session_state[key]``. ``default`` and
    ``label`` must stay constant across reruns or the widget identity changes
    and the state is lost.
    """
    return st.expander(label, expanded=default, key=key)


def _get_browser_user_id() -> str:
    """Anonymous owner id for this session, persisted to a local file."""
    return load_persist_isolate_user_id(st.session_state, DATA_DIR / ISOLATE_USER_ID_FILENAME)


def _isolate_ui_state_path() -> Path:
    return DATA_DIR / ISOLATE_UI_STATE_FILENAME


def _persist_isolate_ui_state() -> None:
    write_isolate_ui_state(_isolate_ui_state_path(), isolate_ui_state_payload(st.session_state))


def _restore_isolate_ui_state() -> None:
    apply_stored_isolate_ui_state(
        st.session_state,
        read_isolate_ui_state(_isolate_ui_state_path()),
    )


def _session_has_mixer_wavs() -> bool:
    return session_mixer_artifacts_ok(
        st.session_state,
        wav_exists=lambda path: Path(path).is_file(),
    )


def _wav_exists(path: str) -> bool:
    return Path(path).is_file()


def _stem_waveform_peaks(path: Path, *, num_points: int = 80) -> list[float]:
    try:
        return waveform_peaks(path, num_points=num_points).tolist()
    except Exception as exc:
        logger.warning("Could not compute waveform peaks for %s: %s", path, exc)
        return []


def _artifact_fingerprint(stem_paths: dict[str, Path]) -> str:
    payload = "|".join(f"{k}:{v}" for k, v in sorted((n, str(p)) for n, p in stem_paths.items()))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _stem_paths_from_artifacts(artifacts_map: dict) -> dict[str, Path]:
    return {
        name: Path(path)
        for name, path in artifacts_map.items()
        if Path(path).exists()
        and name
        not in (
            "guitar_split_diagnostics",
            "stem_presence_diagnostics",
            "bass_bleed_diagnostics",
        )
        and Path(path).suffix.lower() == ".wav"
    }


def _clear_pending_source() -> None:
    st.session_state.pop("isolate_pending_audio_path", None)
    st.session_state.pop("isolate_pending_fp", None)
    st.session_state.pop("isolate_upload_fp", None)
    st.session_state.pop("isolate_duration_sec", None)
    st.session_state.pop("isolate_duration_fp", None)


def _duration_cache_key(audio_path: Path) -> str:
    upload_fp = st.session_state.get("isolate_upload_fp")
    if upload_fp:
        return str(upload_fp)
    try:
        stat = audio_path.stat()
        return f"path:{audio_path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        return f"path:{audio_path.resolve()}"


def _cached_probe_duration_sec(audio_path: Path) -> float | None:
    """Probe file length once per upload; avoid ffprobe on every Streamlit rerun."""
    cache_key = _duration_cache_key(audio_path)
    cached_fp = st.session_state.get("isolate_duration_fp")
    if cached_fp == cache_key and "isolate_duration_sec" in st.session_state:
        return st.session_state.get("isolate_duration_sec")
    duration = probe_duration_sec(audio_path)
    st.session_state["isolate_duration_fp"] = cache_key
    st.session_state["isolate_duration_sec"] = duration
    return duration


def _sync_upload_output_name(uploaded: object) -> None:
    last_fp = st.session_state.get("isolate_upload_fp")
    current_name = st.session_state.get("isolate_output_name", "")
    new_fp, synced_name, changed = sync_output_name_on_upload(
        uploaded,
        last_fp=last_fp,
        output_name=current_name,
    )
    if new_fp is not None:
        st.session_state["isolate_upload_fp"] = new_fp
        if last_fp != new_fp:
            st.session_state.pop("isolate_duration_sec", None)
            st.session_state.pop("isolate_duration_fp", None)
    if changed:
        st.session_state["isolate_output_name"] = synced_name


def _selection_fingerprint(stem_paths: dict[str, Path]) -> str:
    return _artifact_fingerprint(stem_paths)


def _mixer_export_fingerprint(
    stem_names: list[str],
    volumes_db: dict,
    muted: dict,
    soloed: dict,
    master_volume_db: float = DB_DEFAULT,
) -> str:
    parts = [f"master:{float(master_volume_db):.2f}"]
    for name in stem_names:
        parts.append(
            f"{name}:{float(volumes_db.get(name, DB_DEFAULT)):.2f}"
            f":{int(bool(muted.get(name, False)))}:{int(bool(soloed.get(name, False)))}"
        )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _load_bass_bleed_diagnostics(artifacts: dict) -> dict:
    path = artifacts.get("bass_bleed_diagnostics")
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_low_end_recovery_diagnostics(artifacts: dict) -> dict:
    path = artifacts.get("low_end_recovery_diagnostics")
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _render_guitar_fixup_panel(
    stem_paths: dict[str, Path],
    run_dir: Path,
    artifacts_map: dict,
    bass_bleed: dict,
) -> None:
    """Post-separation guitar tweak — no Demucs re-run required."""
    if "guitar" not in stem_paths:
        return

    guitar_path = stem_paths["guitar"]
    run_fp = hashlib.sha256(str(run_dir.resolve()).encode()).hexdigest()[:12]
    has_bass = bool(stem_paths.get("bass") and stem_paths["bass"].is_file())
    backup_exists = has_guitar_backup(guitar_path)
    prerefine_exists = has_guitar_prerefine(guitar_path)
    refined_exists = (run_dir / GUITAR_REFINED_NAME).is_file()
    flagged = bool(bass_bleed.get("flagged"))
    recovery = _load_low_end_recovery_diagnostics(artifacts_map)
    quality = load_guitar_stem_quality(artifacts_map or {})
    fold = load_fold_other_diagnostics(artifacts_map or {})

    debleed_key = f"mixer_fixup_debleed_{run_fp}"
    restore_key = f"mixer_fixup_restore_{run_fp}"
    variant_key = f"mixer_guitar_variant_{run_fp}"
    if debleed_key not in st.session_state:
        st.session_state[debleed_key] = flagged and has_bass
    if restore_key not in st.session_state:
        st.session_state[restore_key] = 0.0

    with st.expander(
        "Guitar fix-up — adjust after separation (no re-run needed)",
        expanded=flagged or bool(recovery.get("attempted")) or prerefine_exists,
    ):
        st.caption(
            "Fix boomy bass bleed or thin low notes on the **guitar** stem only. "
            f"Each apply resets from `{GUITAR_BACKUP_NAME}` (saved on first apply)."
        )

        if quality.get("high_end_energy_share") is not None:
            high_share = quality["high_end_energy_share"]
            competitor_overlap = quality.get("competitor_overlap") or {}
            overlap = max(competitor_overlap.values()) if competitor_overlap else None
            if overlap is None and isinstance(
                quality.get("low_band_energy_share"), (int, float)
            ):
                overlap = quality["low_band_energy_share"]
            st.caption(
                f"Brightness: {'high' if high_share > 0.3 else 'moderate' if high_share > 0.15 else 'low'}"
                f" | Cross-bleed: {'significant' if overlap > 0.3 else 'moderate' if overlap > 0.15 else 'minimal'}"
            )
            if fold.get("folded"):
                st.caption(f"Other folded: {fold.get('reason', 'yes')}")

        if prerefine_exists and refined_exists:
            options = {
                "refined": f"MelBand refined (`{GUITAR_REFINED_NAME}`)",
                "prerefine": f"Pre-refine BS-RoFormer (`{GUITAR_PREREFINE_NAME}`)",
            }
            if variant_key not in st.session_state:
                st.session_state[variant_key] = "refined"
            choice = st.radio(
                "Guitar version",
                options=list(options.keys()),
                format_func=lambda k: options[k],
                key=variant_key,
                help="MelBand refine can soften highs. Compare without re-separating.",
            )
            use_prerefine = choice == "prerefine"
            if st.button(
                "Load selected guitar version",
                key=f"mixer_variant_apply_{run_fp}",
            ):
                result = switch_mixer_guitar_variant(
                    guitar_path=guitar_path,
                    stem_paths=stem_paths,
                    run_dir=run_dir,
                    use_prerefine=use_prerefine,
                )
                if result.ok:
                    st.session_state["isolate_artifacts"] = merge_artifact_updates(
                        st.session_state.get("isolate_artifacts") or artifacts_map,
                        result.artifact_updates,
                    )
                    invalidate_mixer_playback(st.session_state)
                    st.success(result.message)
                    st.rerun()
                else:
                    st.error(result.message)

        if flagged:
            share = bass_bleed.get("low_band_energy_share")
            hint = (
                f"Bass-heavy guitar detected (low-band share {share:.2f}). "
                "Try **Quick de-bleed** below."
                if isinstance(share, (int, float))
                else "Bass-heavy guitar detected — try **Quick de-bleed** below."
            )
            st.info(hint)

        col_debleed, col_restore = st.columns(2)
        with col_debleed:
            st.checkbox(
                "Subtractive bass de-bleed",
                help=(
                    "Subtract leaked bass/drum energy below ~150 Hz using the separated "
                    "bass stem from this run."
                ),
                disabled=not has_bass,
                key=debleed_key,
            )
            if not has_bass:
                st.caption("No bass stem in this run — de-bleed unavailable.")
        with col_restore:
            st.slider(
                "Low-end restore (dB)",
                min_value=0.0,
                max_value=6.0,
                step=1.0,
                help="Optional 60–200 Hz boost after de-bleed if the guitar sounds thin.",
                key=restore_key,
            )

        if recovery.get("attempted"):
            st.caption(
                f"Last fix: {recovery.get('reason', 'applied')} "
                f"(de-bleed={recovery.get('sub_bass_debleed_applied')}, "
                f"restore={recovery.get('harmonic_restore_applied')})"
            )

        btn_apply, btn_quick, btn_reset = st.columns(3)
        with btn_apply:
            apply_clicked = st.button(
                "Apply to guitar",
                type="primary",
                key=f"mixer_fixup_apply_{run_fp}",
            )
        with btn_quick:
            quick_clicked = st.button(
                "Quick de-bleed",
                key=f"mixer_fixup_quick_{run_fp}",
                disabled=not has_bass,
                help="Subtractive bass de-bleed only (no restore). Add restore manually if needed.",
            )
        with btn_reset:
            reset_clicked = st.button(
                "Reset fix-up",
                key=f"mixer_fixup_reset_{run_fp}",
                disabled=not backup_exists,
                help=f"Restore guitar from `{GUITAR_BACKUP_NAME}` before fix-up.",
            )

        result = None
        if apply_clicked:
            with st.spinner("Applying guitar fix-up..."):
                result = apply_mixer_guitar_fixup(
                    guitar_path=guitar_path,
                    stem_paths=stem_paths,
                    run_dir=run_dir,
                    sub_bass_debleed=bool(st.session_state.get(debleed_key)),
                    low_end_restore_db=float(st.session_state.get(restore_key) or 0.0),
                )
        elif quick_clicked:
            with st.spinner("Applying quick de-bleed..."):
                result = apply_mixer_guitar_fixup(
                    guitar_path=guitar_path,
                    stem_paths=stem_paths,
                    run_dir=run_dir,
                    sub_bass_debleed=True,
                    low_end_restore_db=0.0,
                )
            st.session_state[debleed_key] = True
            st.session_state[restore_key] = 0.0
        elif reset_clicked:
            with st.spinner("Resetting guitar fix-up..."):
                result = reset_mixer_guitar_fixup(
                    guitar_path=guitar_path,
                    stem_paths=stem_paths,
                    run_dir=run_dir,
                )

        if result is None:
            return

        if result.ok:
            st.session_state["isolate_artifacts"] = merge_artifact_updates(
                st.session_state.get("isolate_artifacts") or artifacts_map,
                result.artifact_updates,
            )
            invalidate_mixer_playback(st.session_state)
            st.success(result.message)
            st.rerun()
        else:
            st.error(result.message)


def _load_guitar_split_diagnostics(artifacts: dict) -> dict:
    path = artifacts.get("guitar_split_diagnostics")
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _resolved_export_dir() -> Path:
    raw = st.session_state.get(ISOLATE_EXPORT_DIR_KEY)
    if raw:
        path = Path(str(raw)).expanduser()
        if path.exists() or path.parent.exists():
            return path
    path = default_export_dir()
    st.session_state[ISOLATE_EXPORT_DIR_KEY] = str(path)
    return path


def _build_current_mix(
    selected_stem_paths: dict[str, Path],
    run_dir: Path,
    stem_names: list[str],
    volumes_db: dict,
    muted: dict,
    soloed: dict,
    master_volume_db: float = DB_DEFAULT,
) -> Path:
    mix_path = run_dir / "current_mix.wav"
    gains = effective_linear_gains(
        stem_names,
        muted={n: bool(muted.get(n, False)) for n in stem_names},
        soloed={n: bool(soloed.get(n, False)) for n in stem_names},
        volume_db={n: float(volumes_db.get(n, DB_DEFAULT)) for n in stem_names},
        master_volume_db=master_volume_db,
    )
    mix_stems_to_wav(selected_stem_paths, output_path=mix_path, gains=gains)
    fp = _mixer_export_fingerprint(
        stem_names, volumes_db, muted, soloed, master_volume_db
    )
    st.session_state["isolate_mix_ready"] = str(mix_path)
    st.session_state["isolate_mix_fp"] = fp
    return mix_path


def _render_live_mixer(
    stem_paths: dict[str, Path],
    *,
    track_title: str = "",
    base_name: str = "stems",
    run_dir: Path | None = None,
    media_urls: dict[str, str] | None = None,
    download_urls: dict[str, str] | None = None,
) -> dict | None:
    if not component_build_available():
        st.error(
            "Live mixer is not built. "
            "Run: npm install && npm run build in ui/stem_mixer_component/frontend "
            "(or .\\scripts\\dev.ps1 mixer-build)."
        )
        return None

    mixer_paths = ensure_mixer_audio_paths(stem_paths)

    try:
        urls = media_urls if media_urls is not None else stem_media_urls(mixer_paths)
        if download_urls is None:
            download_urls = stem_media_urls(stem_paths, coord_prefix="isolate.download")
    except Exception as exc:
        st.error("Could not prepare track audio for the mixer.")
        with st.expander("Details"):
            st.exception(exc)
        return None

    stem_names = sort_stem_names(stem_paths.keys())
    volumes = st.session_state.setdefault("isolate_volumes_db", {})
    for name in stem_names:
        volumes.setdefault(name, DB_DEFAULT)
    master_db = float(st.session_state.setdefault("isolate_master_volume_db", DB_DEFAULT))
    saved = st.session_state.get("isolate_mixer_state") or {}
    saved_muted = saved.get("muted") or {}
    saved_soloed = saved.get("soloed") or {}

    safe_base = (base_name or "stems").strip() or "stems"
    stems_arg = [
        {
            "id": name,
            "label": stem_display_name(name),
            "url": urls[name],
            "downloadUrl": download_urls.get(name, urls[name]),
            "downloadFilename": f"{safe_base}_{name}.wav",
            "peaks": _stem_waveform_peaks(stem_paths[name]),
            "hint": STEM_HINTS.get(name, ""),
        }
        for name in stem_names
        if name in urls
    ]
    key_src = str(run_dir.resolve()) if run_dir is not None else _artifact_fingerprint(stem_paths)
    mixer_key = "stem_mixer_run_" + hashlib.sha256(key_src.encode()).hexdigest()[:16]
    return stem_mixer(
        stems_arg,
        initial_volumes_db={n: float(volumes.get(n, DB_DEFAULT)) for n in stem_names},
        initial_muted={n: bool(saved_muted.get(n, False)) for n in stem_names},
        initial_soloed={n: bool(saved_soloed.get(n, False)) for n in stem_names},
        initial_master_volume_db=master_db,
        track_title=track_title,
        key=mixer_key,
    )


def _init_track_picker_session() -> None:
    """Seed track picker widget keys from legacy preset or defaults (once)."""
    if st.session_state.get("isolate_track_picker_initialized"):
        return
    migrated = migrate_track_options(st.session_state)
    migrated = promote_default_guitar_option(
        migrated, roformer_available=is_roformer_backend_available()
    )
    for oid in DEMUCS_STEM_CHECKBOX_IDS:
        st.session_state[f"isolate_track_{oid}"] = oid in migrated
    guitar_pick = next((g for g in migrated if g in GUITAR_TRACK_OPTION_IDS), None)
    st.session_state["isolate_guitar_track"] = guitar_pick or "none"
    st.session_state["isolate_vocals_instrumental_only"] = (
        VOCALS_INSTRUMENTAL_OPTION_ID in migrated
    )
    st.session_state["isolate_track_options"] = list(migrated)
    st.session_state["isolate_track_picker_initialized"] = True
    st.session_state.pop("isolate_separation_preset", None)


def _collect_track_options_from_session() -> list[str]:
    if st.session_state.get("isolate_vocals_instrumental_only"):
        return [VOCALS_INSTRUMENTAL_OPTION_ID]
    options: list[str] = []
    for oid in DEMUCS_STEM_CHECKBOX_IDS:
        if st.session_state.get(f"isolate_track_{oid}"):
            options.append(oid)
    guitar = str(st.session_state.get("isolate_guitar_track") or "none")
    if guitar in GUITAR_TRACK_OPTION_IDS:
        options.append(guitar)
    return options


def _render_track_picker(*, persist: dict) -> tuple[list[str], dict, str | None]:
    """Custom-only labeled track picker. Returns (option_ids, resolved, error)."""
    _init_track_picker_session()
    roformer_ok = is_roformer_backend_available()
    st.caption(tracks_picker_help(roformer_available=roformer_ok))
    if not roformer_ok:
        st.info(ROFORMER_BACKEND_UI_HINT)

    vocals_inst = st.checkbox(
        TRACK_OPTIONS[VOCALS_INSTRUMENTAL_OPTION_ID]["label"],
        key="isolate_vocals_instrumental_only",
        **persist,
    )

    if not vocals_inst:
        cols = st.columns(3)
        for idx, option_id in enumerate(DEMUCS_STEM_CHECKBOX_IDS):
            with cols[idx % 3]:
                st.checkbox(
                    TRACK_OPTIONS[option_id]["label"],
                    key=f"isolate_track_{option_id}",
                    **persist,
                )
        normalized_guitar = normalize_guitar_track_selection(
            str(st.session_state.get("isolate_guitar_track") or "none"),
            roformer_available=roformer_ok,
        )
        if st.session_state.get("isolate_guitar_track") != normalized_guitar:
            st.session_state["isolate_guitar_track"] = normalized_guitar
        guitar_radio_ids = guitar_track_radio_ids(roformer_available=roformer_ok)
        guitar_labels = {
            "none": "No guitar",
            **{oid: TRACK_OPTIONS[oid]["label"] for oid in guitar_radio_ids if oid != "none"},
        }
        st.radio(
            "Guitar",
            options=list(guitar_labels.keys()),
            format_func=lambda oid: guitar_labels[oid],
            key="isolate_guitar_track",
            **persist,
        )

    option_ids = _collect_track_options_from_session()
    st.session_state["isolate_track_options"] = list(option_ids)
    preset_error: str | None = None
    try:
        resolved = resolve_track_selection(option_ids)
    except ValueError as exc:
        preset_error = str(exc)
        st.warning(preset_error)
        resolved = resolve_track_selection(list(DEFAULT_TRACK_OPTIONS))
    return option_ids, resolved, preset_error


def _speed_preset_radio_label(preset_id: str) -> str:
    return SPEED_PRESETS[preset_id]["label"]


def _ensure_pending_audio(uploaded: object) -> Path | None:
    """Save upload to disk when fingerprint changes so duration/preview work."""
    fp = upload_fingerprint(uploaded)
    if fp is None:
        return None
    pending = st.session_state.get("isolate_pending_audio_path")
    pending_fp = st.session_state.get("isolate_pending_fp")
    pending_exists = bool(pending and Path(pending).exists())
    if pending_audio_needs_resave(
        uploaded_fp=fp,
        pending_fp=pending_fp if isinstance(pending_fp, str) else None,
        pending_path_exists=pending_exists,
    ):
        if uploaded is not None:
            path = save_upload(uploaded)
            st.session_state["isolate_pending_audio_path"] = str(path)
            st.session_state["isolate_pending_fp"] = fp
            return path
        return None
    return Path(pending) if pending_exists else None


def _active_source_path(uploaded: object) -> Path | None:
    pending = st.session_state.get("isolate_pending_audio_path")
    pending_str = str(pending) if pending else None
    carry = st.session_state.get("carry_over_audio_path")
    carry_str = str(carry) if carry else None
    youtube_on = bool(st.session_state.get("isolate_youtube_enabled"))
    youtube_url = (
        (st.session_state.get("isolate_youtube_url") or "").strip() if youtube_on else ""
    )
    chosen = staged_audio_for_new_tab(
        uploaded=uploaded is not None,
        youtube_url=youtube_url,
        pending_path=pending_str,
        pending_fp=(
            str(st.session_state.get("isolate_pending_fp"))
            if st.session_state.get("isolate_pending_fp")
            else None
        ),
        pending_exists=bool(pending_str and Path(pending_str).exists()),
        carry_path=carry_str,
        carry_exists=bool(carry_str and Path(carry_str).exists()),
    )
    return Path(chosen) if chosen else None


def _st_version() -> tuple[int, int, int]:
    """Return parsed Streamlit version as (major, minor, patch)."""
    try:
        from packaging import version as _pv

        v = _pv.Version(st.__version__)
        return (v.major, v.minor, v.micro)
    except Exception:
        return (0, 0, 0)


def _st_at_least(major: int, minor: int, patch: int = 0) -> bool:
    return _st_version() >= (major, minor, patch)


def _closed_selectbox(label: str, options: list[str], *, key: str, help: str | None = None):
    """Dropdown that does not accept typed free-text (Streamlit ≥1.55 combobox)."""
    kwargs: dict = {
        "label": label,
        "options": options,
        "key": key,
        "accept_new_options": False,
    }
    if help:
        kwargs["help"] = help
    if _st_at_least(1, 55, 0):
        return st.selectbox(**kwargs, filter_mode=None)
    return st.selectbox(**kwargs)


def _render_region_controls(audio_path: Path | None) -> tuple[float, float | None, str | None]:
    """
    Region sliders (Advanced). Returns (start_sec, max_duration_sec, region_label).

    ``max_duration_sec`` is None for full-file processing. Preview is rendered
    on the Basic path — not here.
    """
    if audio_path is None or not audio_path.exists():
        return 0.0, None, None

    duration = _cached_probe_duration_sec(audio_path)
    if duration is None:
        st.caption("Length: unknown — full file will be processed.")
        return 0.0, None, None

    st.caption(f"Length: **{format_time_sec(duration)}** ({duration:.1f} s)")

    region_key = f"isolate_region_{st.session_state.get('isolate_pending_fp') or st.session_state.get('isolate_upload_fp', 'none')}"
    if region_key not in st.session_state:
        st.session_state[region_key] = (0.0, float(duration))

    start_default, end_default = st.session_state[region_key]
    start_default, end_default = clamp_region_bounds(
        start_default, end_default, duration, min_length=MIN_REGION_SEC
    )

    start_col, end_col = st.columns(2)
    with start_col:
        start_sec = st.slider(
            f"Start ({format_time_sec(start_default)})",
            min_value=0.0,
            max_value=float(duration),
            value=float(start_default),
            step=1.0,
            format="%.0f",
            key=f"{region_key}_start",
        )
    with end_col:
        end_sec = st.slider(
            f"End ({format_time_sec(end_default)})",
            min_value=float(MIN_REGION_SEC),
            max_value=float(duration),
            value=float(end_default),
            step=1.0,
            format="%.0f",
            key=f"{region_key}_end",
        )
    start_sec, end_sec = clamp_region_bounds(
        start_sec, end_sec, duration, min_length=MIN_REGION_SEC
    )
    st.session_state[region_key] = (start_sec, end_sec)

    length = end_sec - start_sec
    region_label = format_region_label(start_sec, length)
    st.caption(f"**{region_label}** ({length:.0f} s)")

    if length < MIN_REGION_SEC:
        st.error(f"Section must be at least {MIN_REGION_SEC:.0f} seconds.")
        return start_sec, None, region_label

    # Leave start/end at the file bounds → process the whole file (no trim).
    if start_sec <= 0.5 and end_sec >= duration - 0.5:
        return 0.0, None, None

    return start_sec, length, region_label


def _render_section_preview(
    audio_path: Path | None,
    start_sec: float,
    max_duration_sec: float | None,
    region_label: str | None,
) -> None:
    """Play the section that will be isolated (or the full file)."""
    if audio_path is None or not audio_path.exists():
        return
    fp = str(
        st.session_state.get("isolate_pending_fp")
        or st.session_state.get("isolate_upload_fp")
        or audio_path.name
    )
    if max_duration_sec is None:
        st.caption("Preview — full file (what will be processed)")
        try:
            st.audio(str(audio_path))
        except Exception:
            pass
        return
    label = region_label or format_region_label(start_sec, float(max_duration_sec))
    st.caption(f"Preview — **{label}** ({float(max_duration_sec):.0f} s)")
    try:
        with st.spinner("Preparing section preview…"):
            preview = ensure_region_preview_wav(
                audio_path,
                start_sec=start_sec,
                length_sec=float(max_duration_sec),
                fingerprint=fp,
                cache_dir=DATA_DIR / "region_previews",
            )
        st.audio(str(preview))
    except Exception:
        try:
            st.audio(str(audio_path))
        except Exception:
            pass


def _persist_kwargs() -> dict:
    """Keep isolate widgets across page switches when Streamlit supports it."""
    try:
        import inspect

        if "persist_state" in inspect.signature(st.radio).parameters:
            return {"persist_state": "session"}
    except Exception:
        pass
    return {}


def _render_separation_controls() -> dict:
    """New tab: source, tracks, speed, Advanced, section preview."""
    apply_pending_output_name(st.session_state)
    apply_pending_youtube_url(st.session_state)
    apply_youtube_output_name_sync(st.session_state)
    if st.session_state.get("isolate_speed_preset") not in SPEED_PRESETS:
        st.session_state["isolate_speed_preset"] = DEFAULT_SPEED_PRESET
    persist = _persist_kwargs()

    uploaded = st.file_uploader(
        "Upload MP3 / WAV / FLAC / M4A",
        type=AUDIO_UPLOAD_TYPES,
        key=f"isolate_upload_{st.session_state.get('isolate_upload_key', 0)}",
    )
    _sync_upload_output_name(uploaded)
    if uploaded is not None:
        _ensure_pending_audio(uploaded)

    youtube_error: str | None = None
    youtube_enabled = st.checkbox(
        "Download from YouTube",
        value=False,
        key="isolate_youtube_enabled",
        help=(
            "Off by default. Enable only if you have rights to the audio. "
            "Arbitrary URLs are rejected."
        ),
        **persist,
    )
    youtube_url = ""
    if youtube_enabled:
        url_row = st.columns([4, 1], vertical_alignment="bottom")
        with url_row[0]:
            youtube_url = st.text_input(
                "Or paste a YouTube URL",
                key="isolate_youtube_url",
                **persist,
            )
        with url_row[1]:
            if st.button(
                "Search songs",
                key="isolate_youtube_search_open_btn",
                width="stretch",
                help="Open a search panel to find a public video by song or artist.",
            ):
                st.session_state[ISOLATE_YOUTUBE_SEARCH_OPEN_KEY] = True
                st.rerun()
        if st.session_state.get(ISOLATE_YOUTUBE_SEARCH_OPEN_KEY):
            _youtube_search_dialog()
        st.caption(YOUTUBE_DISCLAIMER)
        url_ready = youtube_url.strip()
        if url_ready and not is_youtube_url(url_ready):
            youtube_error = "Only YouTube URLs are allowed."
            st.error(youtube_error)
        elif url_ready and st.button(
            "Download audio",
            key="isolate_youtube_download",
            help="Fetch the audio now so you can preview it before starting isolation.",
        ):
            try:
                with st.spinner("Downloading YouTube audio…"):
                    path = download_youtube_audio(url_ready, run_output_dir())
                st.session_state["isolate_pending_audio_path"] = str(path)
                st.session_state["isolate_pending_fp"] = f"youtube:{url_ready}"
                st.session_state["isolate_upload_fp"] = f"youtube:{url_ready}"
                apply_youtube_output_name_sync(
                    st.session_state,
                    downloaded_stem=path.stem,
                    apply_now=True,
                )
                st.rerun()
            except YouTubeDownloadError as exc:
                youtube_error = str(exc)
                st.error(youtube_error)
            except Exception as exc:
                youtube_error = f"YouTube download failed: {exc}"
                st.error(youtube_error)
        pending = st.session_state.get("isolate_pending_audio_path")
        pending_fp = st.session_state.get("isolate_pending_fp")
        if (
            pending
            and Path(pending).exists()
            and isinstance(pending_fp, str)
            and pending_fp == f"youtube:{url_ready}"
        ):
            st.caption(f"Ready: **{Path(pending).stem}**")
    elif getattr(sys, "frozen", False):
        st.caption(
            "YouTube download is off in this installer build. Enable it above if you "
            "have rights to the audio."
        )

    carry_over_path = st.session_state.get("carry_over_audio_path")
    carry_over_name = st.session_state.get("carry_over_audio_name")
    if not uploaded and carry_over_path and Path(carry_over_path).exists():
        st.caption(
            f"Using audio carried over from Tab PDF: **{carry_over_name}**. "
            "Upload a file above to use something else instead."
        )
    default_name = Path(uploaded.name).stem if uploaded else Path(carry_over_name or "").stem
    if default_name and not st.session_state.get("isolate_output_name"):
        st.session_state["isolate_output_name"] = default_name

    audio_path = _active_source_path(uploaded)

    st.text_input(
        "Output name",
        help="Used for downloaded file names. Defaults to the uploaded file's name.",
        key="isolate_output_name",
        max_chars=100,
        **persist,
    )
    staged_name = st.session_state.get("isolate_output_name")
    if staged_name:
        sanitized_name = " ".join(staged_name.split())
        if sanitized_name != staged_name:
            st.caption(f"Will be saved as: **{sanitized_name}**")

    start_sec, max_duration_sec, region_label = 0.0, None, None
    if audio_path and audio_path.exists():
        st.markdown("**Section (optional)**")
        start_sec, max_duration_sec, region_label = _render_region_controls(audio_path)
        _render_section_preview(audio_path, start_sec, max_duration_sec, region_label)

    track_options, resolved, preset_error = _render_track_picker(persist=persist)
    custom_stems = list(resolved.get("stems") or [])
    if resolved["caveat"]:
        st.caption(resolved["caveat"])

    probe = (
        get_desktop_probe()
        if st.session_state.get("isolate_options_expanded")
        else get_desktop_probe_without_torch()
    )
    speed_id = st.radio(
        "Speed",
        options=list(SPEED_PRESETS.keys()),
        format_func=_speed_preset_radio_label,
        key="isolate_speed_preset",
        horizontal=True,
        **persist,
    )
    speed = resolve_speed_preset(speed_id, probe, model=resolved["model"])
    if speed["help"]:
        st.caption(speed["help"])
    if job_requires_roformer_backend(resolved["model"]):
        st.caption(ROFORMER_SPEED_PRESET_NOTE)

    applied = f"{speed['id']}:{resolved['model']}"
    if st.session_state.get("isolate_speed_applied") != applied:
        st.session_state["isolate_speed_applied"] = applied
        st.session_state["isolate_quality"] = speed["quality"]
        st.session_state["isolate_device"] = speed["device"]

    device_options = desktop_device_options(probe)
    if st.session_state.get("isolate_device") not in device_options:
        st.session_state["isolate_device"] = device_options[0]

    with _stateful_expander(
        "Advanced options", key="isolate_options_expanded", default=False
    ):
        st.caption(desktop_system_summary(probe))
        st.caption(desktop_recommend_caption(probe))
        quality = _closed_selectbox(
            "Quality",
            ["fast", "balanced", "high", "extreme"],
            key="isolate_quality",
            help="Higher quality is slower, especially on CPU.",
        )
        device = _closed_selectbox(
            "Device",
            device_options,
            key="isolate_device",
            help=(
                "GPU: NVIDIA CUDA on Windows; Apple GPU (MPS) on Apple Silicon "
                "with ≥12 GB RAM. CPU is always available."
            ),
        )
        # Opt-in until eval/lead_rhythm Stage-1 3-clip listen beats stock 6s.
        st.checkbox(
            "Use guitar-focused Demucs weights (experimental)",
            help=(
                "Optional guitar-focused htdemucs_6s weights (~330 MB first download, "
                "cached under TORCH_HOME/checkpoints). Falls back to stock if download "
                "or load fails. Piano/synth and bass can still bleed into guitar. "
                "Meta Demucs weights are provided for scientific/research use."
            ),
            key="isolate_guitar_ft",
            **persist,
        )
        if resolved["model"] == "htdemucs_6s":
            st.checkbox(
                "Two-pass guitar isolation (experimental)",
                help=(
                    "Runs a 4-stem split first, then isolates guitar from the leftover mix. "
                    "About twice as slow. Can reduce competing vocals/drums/bass in the "
                    "guitar stem. Stay opt-in until the stage-1 listen pass."
                ),
                key="isolate_two_pass",
                **persist,
            )
            st.checkbox(
                "Refine guitar with MelBand specialist (experimental)",
                help=(
                    "Second-pass guitar extraction (becruily MelBand-Roformer, ~45 MB first "
                    "download). De-bleeds the Demucs guitar stem. Skipped when the refine "
                    "runtime is unavailable."
                ),
                key="isolate_guitar_refine",
                **persist,
            )
        elif resolved["model"] == "bs_roformer_sw" and resolved.get("guitar_refine"):
            st.caption(
                "BS-RoFormer-SW runs first; MelBand refine follows when guitar is selected."
            )
        st.caption(
            "Guitar low-end fix-up (bass de-bleed, restore) lives on the **Mixer** tab after "
            "separation — no need to re-run Demucs. MelBand refine improves isolation but can "
            "soften highs — use **Guitar (BS-RoFormer)** without refine if guitar sounds dull."
        )

    quality = st.session_state.get("isolate_quality", speed["quality"])
    device = st.session_state.get("isolate_device", speed["device"])
    output_name = st.session_state.get("isolate_output_name", default_name or "")
    guitar_checkpoint = None
    if st.session_state.get("isolate_guitar_ft") and resolved["model"] == "htdemucs_6s":
        guitar_checkpoint = "htdemucs_6s_guitar_ft"
    two_pass = bool(
        st.session_state.get("isolate_two_pass") and resolved["model"] == "htdemucs_6s"
    )
    guitar_refine = bool(resolved.get("guitar_refine")) or bool(
        st.session_state.get("isolate_guitar_refine")
        and resolved["model"] in {"htdemucs_6s", "bs_roformer_sw", "melband_roformer_guitar"}
    )
    return {
        "model": resolved["model"],
        "two_stems": resolved["two_stems"],
        "custom_stems": custom_stems,
        "track_options": list(track_options),
        "error": preset_error or youtube_error,
        "quality": quality,
        "device": device,
        "start_sec": start_sec,
        "max_duration_sec": max_duration_sec,
        "uploaded": uploaded,
        "output_name": output_name,
        "region_label": region_label,
        "guitar_checkpoint": guitar_checkpoint,
        "two_pass": two_pass,
        "guitar_refine": guitar_refine,
        "low_end_restore_db": 0.0,
        "sub_bass_debleed": False,
        "emit_stems": list(resolved["emit_stems"]) if resolved.get("emit_stems") else None,
        "fold_other_into_guitar": bool(resolved.get("fold_other_into_guitar", True)),
        "fold_other_mode": str(resolved.get("fold_other_mode") or "best_effort"),
        "youtube_url": youtube_url.strip() if youtube_enabled else "",
        "tracks_label": resolved.get("tracks") or "",
        "preset_label": resolved.get("label") or "",
        "audio_path": audio_path,
    }


def _ffmpeg_install_hint() -> str:
    if sys.platform == "darwin":
        return "Install ffmpeg: brew install ffmpeg"
    if sys.platform.startswith("win"):
        return "Install ffmpeg: winget install Gyan.FFmpeg (full/shared build, not essentials-only)"
    return "Install ffmpeg: sudo apt install ffmpeg (or your distro equivalent)"


def _rehydrate_artifacts_from_disk(browser_id: str | None) -> None:
    """Restore mixer results from last-viewed run, else the latest library row."""
    rows = _library_rows_available(browser_id)
    row = select_rehydrate_row(st.session_state, rows, wav_exists=_wav_exists)
    if row is None:
        return
    _apply_library_row(row, viewing_mode="latest", reopen_name=False)


def _refresh_isolate_from_disk(browser_id: str | None) -> None:
    ensure_worker_started()
    _rehydrate_artifacts_from_disk(browser_id)
    _persist_isolate_ui_state()
    st.rerun()


def _open_mixer_workspace() -> None:
    """Request Mixer on the next full run, before ``st.tabs`` is instantiated."""
    st.session_state[WORKSPACE_NEXT_KEY] = "Mixer"


def _open_queue_workspace() -> None:
    """Request Queue on the next full run, before ``st.tabs`` is instantiated."""
    st.session_state[WORKSPACE_NEXT_KEY] = "Queue"


def _ensure_workspace_tab(*, has_artifacts: bool) -> None:
    apply_workspace_tab(st.session_state, has_artifacts=has_artifacts)


def _worker_jobs_active() -> bool:
    """True while a separation job is queued, starting, or running."""
    try:
        return bool(worker_busy() or active_job_id() or queued_job_ids())
    except Exception:
        return False


def _update_global_loading_flag(
    *,
    job_running: bool,
    tab_changed: bool,
    nav_requested: bool,
) -> None:
    """Tell the global overlay (app.py) whether to dim + show the spinner.

    Show it only for a real page/tab switch or an in-progress job — a plain
    button rerun must not flash the overlay.
    """
    show = job_running or tab_changed or nav_requested
    st.session_state["_show_global_loading"] = bool(show)


def _request_loading_overlay() -> None:
    """Ask the global overlay to show while a cross-page switch is in flight."""
    st.session_state["_nav_loading"] = True


def _staged_source_name() -> str:
    pending = st.session_state.get("isolate_pending_audio_path")
    if pending and Path(str(pending)).exists():
        return Path(str(pending)).stem
    return "New file"


def _render_running_progress(status: dict) -> None:
    view = running_progress_view(status, time.time())
    st.progress(min(1.0, max(0.0, float(view["percent"]))))
    bits = [str(view.get("label") or ""), str(view.get("eta_line") or "")]
    st.markdown(" · ".join(b for b in bits if b))
    if view.get("hint"):
        st.caption(view["hint"])


def _job_source_title(job: dict) -> str:
    title = job.get("title") or str(job.get("id") or "")[:8] or "track"
    kind = infer_source_kind(
        source_kind=job.get("source_kind"),
        source_fingerprint=job.get("source_fingerprint"),
    )
    return format_source_title(str(title), kind)


def _render_job_queue_panel() -> None:
    ensure_worker_started()
    parts = partition_queue_jobs(jobs_visible_in_queue(list_jobs(limit=30)))
    if parts["empty"]:
        st.caption("No jobs yet.")
        return
    if parts["succeeded"]:
        if st.button("Delete all finished", key="isolate_delete_all_finished"):
            dirs = delete_all_finished_jobs(parts["succeeded"])
            _clear_mixer_if_run_deleted(dirs)
            st.rerun()
    waiting_ids = queued_job_ids()
    active_id = active_job_id()
    stopping_previous = False
    if active_id and worker_busy():
        active_status = read_status(active_id) or {}
        stopping_previous = is_stopping_previous_job(
            active_id,
            str(active_status.get("status") or ""),
        )
    for job in parts["in_flight"]:
        with st.container(border=True):
            _render_queue_job_row(
                job,
                waiting_ids=waiting_ids,
                stopping_previous=stopping_previous,
            )
    for job in parts["succeeded"]:
        with st.container(border=True):
            _render_queue_job_row(
                job,
                waiting_ids=waiting_ids,
                stopping_previous=stopping_previous,
            )


def _clear_mixer_if_run_deleted(run_dirs: list[str] | str | None) -> None:
    if not run_dirs:
        return
    targets = {str(run_dirs)} if isinstance(run_dirs, str) else {str(d) for d in run_dirs if d}
    current = st.session_state.get("isolate_run_dir") or st.session_state.get(
        "isolate_viewing_run_dir"
    )
    if current and str(current) in targets:
        _clear_loaded_mixer()
        _persist_isolate_ui_state()


def _render_job_failure(
    title: str,
    raw_error: str | None,
    *,
    detail_key: str,
    inline_caption: bool = False,
) -> None:
    """Short summary plus full error text in an expander."""
    summary = format_job_error(raw_error)
    detail = (raw_error or "").strip() or summary
    if inline_caption:
        st.caption(summary)
    else:
        st.error(f"**{title}** failed: {summary}")
    if detail:
        with st.expander("Details", expanded=True, key=detail_key):
            st.code(detail)


def _render_queue_job_row(
    job: dict,
    *,
    waiting_ids: list[str],
    stopping_previous: bool,
) -> None:
    status = job.get("status", "unknown")
    title = _job_source_title(job)
    job_id = str(job.get("id") or "")
    label = "done" if status == "succeeded" else status
    if status == "running":
        n_actions = 2
    elif status == "paused":
        n_actions = 2
    elif status == "succeeded":
        n_actions = 2
    else:
        n_actions = 1
    cols = st.columns([4, *([1] * n_actions)])
    with cols[0]:
        st.write(f"**{title}** — {label}")
        if status == "failed":
            _render_job_failure(
                title,
                job.get("error") or job.get("message"),
                detail_key=f"job_fail_details_{job_id}",
                inline_caption=True,
            )
        elif status == "queued":
            st.caption(
                queued_wait_caption(
                    job_id,
                    waiting_ids,
                    stopping_previous=stopping_previous,
                )
            )
        elif status == "cancelled":
            st.caption("Removed from queue")
        elif status == "paused":
            st.caption(paused_job_caption(job.get("completed_stages")))
        elif status == "pausing":
            st.caption("Pausing…")
        elif status == "running":
            st.caption("Separating…")
    if status == "succeeded" and job_id:
        with cols[1]:
            if st.button("Open in Mixer", key=f"open_mixer_{job_id}"):
                fresh = read_status(job_id) or job
                if apply_succeeded_job_to_session(
                    st.session_state,
                    fresh,
                    viewing_mode=job_id,
                ):
                    run_dir = fresh.get("run_dir")
                    if run_dir:
                        st.session_state["isolate_listen_applied_dir"] = str(run_dir)
                    _open_mixer_workspace()
                    _persist_isolate_ui_state()
                    st.rerun()
                else:
                    st.caption("Those files are no longer available.")
        with cols[2]:
            if st.button("Delete", key=f"delete_finished_{job_id}"):
                result = delete_finished_job(read_status(job_id) or job)
                _clear_mixer_if_run_deleted(result.get("run_dir"))
                st.rerun()
        return
    if status == "running" and job_id:
        with cols[1]:
            if st.button(
                "Pause",
                key=f"pause_job_{job_id}",
                help=(
                    "Pauses after the current step finishes (or stops heavy processing). "
                    "Resume continues from the last saved step."
                ),
            ):
                pause_job(job_id)
                ensure_worker_started()
                st.rerun()
        with cols[2]:
            if st.button(
                "Stop",
                key=f"stop_job_{job_id}",
                help="Cancel and remove this job.",
            ):
                remove_job(job_id)
                ensure_worker_started()
                st.rerun()
        return
    if status == "paused" and job_id:
        with cols[1]:
            if st.button("Resume", key=f"resume_job_{job_id}"):
                resume_job(job_id)
                ensure_worker_started()
                st.rerun()
        with cols[2]:
            if st.button("Remove", key=f"remove_paused_{job_id}"):
                remove_job(job_id)
                ensure_worker_started()
                st.rerun()
        return
    with cols[1]:
        if job_id and st.button(
            "Remove",
            key=f"remove_job_{job_id}",
            help="Drop this job from the list.",
        ):
            remove_job(job_id)
            ensure_worker_started()
            st.rerun()


def _render_status_strip(jobs: list) -> None:
    """Running / queued / failed only. Empty when idle."""
    running = None
    failed = None
    for job in jobs:
        jid = job.get("id")
        if not jid:
            continue
        fresh = read_status(jid) or job
        status = fresh.get("status")
        if status == "running" and running is None:
            running = fresh
        elif status == "failed" and failed is None:
            failed = fresh
    waiting_ids = queued_job_ids()
    active_id = active_job_id()
    stopping_previous = False
    if active_id and worker_busy():
        active_status = read_status(active_id) or {}
        stopping_previous = is_stopping_previous_job(
            active_id,
            str(active_status.get("status") or ""),
        )
    show_queued = running is None and failed is None and bool(waiting_ids)
    if not (running or failed or show_queued or stopping_previous):
        return
    with st.container(border=True, key="isolate_status_strip"):
        if running:
            st.info(f"Separating **{_job_source_title(running)}**")
            _render_running_progress(running)
        elif failed:
            _render_job_failure(
                _job_source_title(failed),
                failed.get("error"),
                detail_key="isolate_status_fail_details",
            )
        elif stopping_previous:
            st.caption(status_strip_waiting_caption(waiting_ids, stopping_previous=True))
        elif show_queued:
            st.caption(
                status_strip_waiting_caption(waiting_ids, stopping_previous=False)
            )


@st.fragment(run_every=1.0)
def _poll_running_jobs() -> None:
    """Keep progress visible across page switches; apply finished jobs when unpinned."""
    ensure_worker_started()
    jobs = list_jobs(limit=15)
    if "isolate_consumed_job_ids" not in st.session_state:
        consumed_ids = None
    else:
        consumed_ids = list(st.session_state.get("isolate_consumed_job_ids") or [])
    viewing = st.session_state.get("isolate_viewing_job_id")
    plan = plan_isolate_job_poll(
        jobs,
        consumed_ids=consumed_ids,
        viewing_id=viewing if isinstance(viewing, str) else None,
        form_drawn=bool(st.session_state.get("_isolate_form_drawn")),
    )
    st.session_state["isolate_consumed_job_ids"] = plan["consumed_ids"]

    job = plan["apply_job"]
    applied = False
    if job:
        jid = str(job.get("id") or "")
        fresh = read_status(jid) or job
        st.session_state["isolate_consumed_job_id"] = jid
        if plan["notify_only"]:
            title = fresh.get("title") or "track"
            st.session_state["isolate_flash"] = (
                f"**{title}** finished — choose it under Listening to…"
            )
            _open_mixer_workspace()
            applied = True
        elif apply_succeeded_job_to_session(st.session_state, fresh, viewing_mode="latest"):
            produced = [
                n
                for n, path in (fresh.get("artifacts") or {}).items()
                if Path(path).suffix.lower() == ".wav"
                and not str(n).endswith("_diagnostics")
            ]
            st.session_state["isolate_flash"] = (
                f"Separated {len(produced)} tracks. Live mixer and downloads are on Mixer."
            )
            st.session_state["isolate_listen_applied_dir"] = fresh.get("run_dir")
            _open_mixer_workspace()
            applied = True

    if "isolate_notified_job_ids" not in st.session_state:
        notified_ids = None
    else:
        notified_ids = list(st.session_state.get("isolate_notified_job_ids") or [])
    notified_ids, pending_notify = jobs_needing_os_notify(jobs, notified_ids)
    st.session_state["isolate_notified_job_ids"] = notified_ids
    failed_flash = False
    for nj in pending_notify:
        message = os_notify_message(nj)
        if message is None:
            continue
        desktop_notify(message[0], message[1])
        if nj.get("status") == "failed" and not applied:
            fail_title = nj.get("title") or "track"
            st.session_state["isolate_flash"] = f"**{fail_title}** failed — see Queue."
            failed_flash = True

    if (plan["rerun"] and applied) or failed_flash:
        _persist_isolate_ui_state()
        st.rerun()

    _render_status_strip(jobs)


@st.fragment(run_every=1.0)
def _queue_tab_fragment() -> None:
    _render_job_queue_panel()


@st.fragment
def _mixer_and_downloads_fragment(
    stem_paths: dict[str, Path],
    *,
    base_name: str,
    run_dir: Path,
    media_urls: dict[str, str],
    download_urls: dict[str, str],
) -> None:
    """Mixer and downloads — fragment-scoped so the mixer does not remount the page."""
    selected_stem_paths = stem_paths
    mixer_state = _render_live_mixer(
        selected_stem_paths,
        track_title=base_name,
        base_name=base_name,
        run_dir=run_dir,
        media_urls=media_urls,
        download_urls=download_urls,
    )
    if mixer_state:
        st.session_state["isolate_mixer_state"] = mixer_state
        if "volumesDb" in mixer_state:
            st.session_state["isolate_volumes_db"] = {
                k: float(v) for k, v in mixer_state["volumesDb"].items()
            }
        if "masterVolumeDb" in mixer_state:
            st.session_state["isolate_master_volume_db"] = float(
                mixer_state["masterVolumeDb"]
            )

    st.subheader("Downloads")
    if not selected_stem_paths:
        st.info("No tracks available to download.")
        return

    stem_names = sort_stem_names(selected_stem_paths.keys())
    state = st.session_state.get("isolate_mixer_state") or {}
    volumes_db = state.get("volumesDb") or st.session_state.get("isolate_volumes_db") or {}
    muted = state.get("muted") or {n: False for n in stem_names}
    soloed = state.get("soloed") or {n: False for n in stem_names}
    master_volume_db = float(
        state.get("masterVolumeDb", st.session_state.get("isolate_master_volume_db", DB_DEFAULT))
    )
    export_fp = _mixer_export_fingerprint(
        stem_names, volumes_db, muted, soloed, master_volume_db
    )
    ready = st.session_state.get("isolate_mix_ready")
    mix_fresh = (
        ready
        and Path(ready).exists()
        and st.session_state.get("isolate_mix_fp") == export_fp
    )

    if not mix_fresh:
        try:
            with st.spinner("Building current mix..."):
                _build_current_mix(
                    selected_stem_paths,
                    run_dir,
                    stem_names,
                    volumes_db,
                    muted,
                    soloed,
                    master_volume_db,
                )
            ready = st.session_state.get("isolate_mix_ready")
        except Exception as exc:
            st.session_state.pop("isolate_mix_ready", None)
            st.session_state.pop("isolate_mix_fp", None)
            ready = None
            st.warning("Could not build current mix export.")
            with st.expander("Details"):
                st.exception(exc)

    _render_downloads_panel(
        selected_stem_paths,
        base_name=base_name,
        ready=ready,
    )


def _save_all_tracks(selected_stem_paths: dict[str, Path], export_root: Path, base_name: str, fmt: str) -> None:
    dest = export_song_dir(export_root, str(base_name))
    export_tracks_to_folder(selected_stem_paths, dest, str(base_name), fmt)
    st.session_state["isolate_last_export_path"] = str(dest)
    st.success(f"Download finished — saved to {dest}")


def _save_current_mix(ready: str, export_root: Path, base_name: str, fmt: str) -> None:
    dest_file = export_mix_to_folder(
        Path(ready),
        export_song_dir(export_root, str(base_name)),
        f"{base_name}_current_mix.wav",
        fmt,
    )
    st.session_state["isolate_last_export_path"] = str(dest_file.parent)
    st.success(f"Download finished — saved to {dest_file}")


def _download_format_widget() -> str:
    """Format selector used by the Downloads panel. Returns an EXPORT_FORMATS key."""
    if _st_at_least(1, 41, 0):
        fmt = st.segmented_control(
            "Export format",
            options=list(EXPORT_FORMATS),
            format_func=lambda f: EXPORT_FORMAT_LABELS[f],
            default="wav",
            key="isolate_download_format",
            help="WAV is lossless; other formats are handled automatically.",
        )
        return fmt or "wav"
    fmt = st.selectbox(
        "Export format",
        options=list(EXPORT_FORMATS),
        format_func=lambda f: EXPORT_FORMAT_LABELS[f],
        index=0,
        key="isolate_download_format",
        help="WAV is lossless; other formats are converted with ffmpeg.",
    )
    return fmt or "wav"


def _render_downloads_panel(
    selected_stem_paths: dict[str, Path],
    *,
    base_name: str,
    ready: str | None,
) -> None:
    """Save location and export to folder — equal-width button rows."""
    export_root = _resolved_export_dir()
    with st.container(border=True):
        st.caption(f"Save to: {export_root}")
        choose_col, open_col = st.columns(2)
        with choose_col:
            if st.button(
                "Choose folder",
                key="isolate_choose_export_dir",
                width="stretch",
            ):
                picked = choose_export_dir()
                if picked:
                    st.session_state[ISOLATE_EXPORT_DIR_KEY] = str(picked)
                    _persist_isolate_ui_state()
                else:
                    st.caption("Folder picker was cancelled or is not available.")
        with open_col:
            if st.button(
                "Open folder",
                key="isolate_open_export_dir",
                width="stretch",
            ):
                last = st.session_state.get("isolate_last_export_path")
                target = Path(str(last)) if last else export_root
                if not open_path_in_os(target):
                    st.warning("Could not open that folder.")

        st.divider()
        fmt = _download_format_widget()
        if ready:
            save_col, mix_col = st.columns(2)
            with save_col:
                if st.button(
                    "Save all tracks",
                    type="primary",
                    key="isolate_save_tracks",
                    width="stretch",
                ):
                    with st.spinner(f"Converting tracks to {fmt}..."):
                        _save_all_tracks(selected_stem_paths, export_root, str(base_name), fmt)
            with mix_col:
                if st.button(
                    "Save current mix",
                    key="isolate_save_mix",
                    width="stretch",
                ):
                    with st.spinner(f"Converting mix to {fmt}..."):
                        _save_current_mix(str(ready), export_root, str(base_name), fmt)
        else:
            if st.button(
                "Save all tracks",
                type="primary",
                key="isolate_save_tracks",
                width="stretch",
            ):
                with st.spinner(f"Converting tracks to {fmt}..."):
                    _save_all_tracks(selected_stem_paths, export_root, str(base_name), fmt)


def _resolve_audio_for_job(choice: dict) -> tuple[Path | None, str | None]:
    """Return (audio path, error). Error is None when a path is ready or there is no source."""
    uploaded = choice.get("uploaded")
    youtube_url = (choice.get("youtube_url") or "").strip()
    pending = st.session_state.get("isolate_pending_audio_path")
    carry_over_path = st.session_state.get("carry_over_audio_path")

    if youtube_url:
        if not is_youtube_url(youtube_url):
            return None, "Only YouTube URLs are allowed."
        already = (
            pending
            and Path(pending).exists()
            and st.session_state.get("isolate_pending_fp") == f"youtube:{youtube_url}"
        )
        if already:
            audio = Path(pending)
            new_name = apply_youtube_output_name_sync(
                st.session_state,
                downloaded_stem=audio.stem,
                apply_now=False,
            )
            if new_name:
                choice["output_name"] = new_name
            elif not str(choice.get("output_name") or "").strip():
                choice["output_name"] = audio.stem
            return audio, None
        out = run_output_dir()
        try:
            with st.spinner("Downloading YouTube audio…"):
                path = download_youtube_audio(youtube_url, out)
            st.session_state["isolate_pending_audio_path"] = str(path)
            st.session_state["isolate_pending_fp"] = f"youtube:{youtube_url}"
            st.session_state["isolate_upload_fp"] = f"youtube:{youtube_url}"
            new_name = apply_youtube_output_name_sync(
                st.session_state,
                downloaded_stem=path.stem,
                apply_now=False,
            )
            if new_name:
                choice["output_name"] = new_name
            elif not str(choice.get("output_name") or "").strip():
                choice["output_name"] = path.stem
            return path, None
        except YouTubeDownloadError as exc:
            return None, str(exc)
        except Exception as exc:
            return None, f"YouTube download failed: {exc}"

    if uploaded and pending and Path(pending).exists():
        return Path(pending), None
    if uploaded:
        path = save_upload(uploaded)
        st.session_state["isolate_pending_audio_path"] = str(path)
        fp = upload_fingerprint(uploaded)
        if fp:
            st.session_state["isolate_pending_fp"] = fp
        return path, None
    if carry_over_path and Path(carry_over_path).exists():
        return Path(carry_over_path), None
    if choice.get("audio_path") and Path(choice["audio_path"]).exists():
        return Path(choice["audio_path"]), None
    return None, None


def _enqueue_confirmed_job(choice: dict, audio_path: Path) -> None:
    start_sec = float(choice.get("start_sec") or 0.0)
    max_duration_sec = choice.get("max_duration_sec")
    region_label = choice.get("region_label")
    output_name = resolve_youtube_job_name(
        choice.get("output_name") or "",
        choice.get("youtube_url") or "",
        audio_path.stem,
    )

    try:
        file_dur = probe_duration_sec(audio_path)
        if max_duration_sec is not None:
            _, validated_length, _ = resolve_region(
                file_dur,
                start_sec,
                start_sec + float(max_duration_sec),
            )
            max_duration_sec = float(validated_length)
        job_audio_sec = (
            float(max_duration_sec)
            if max_duration_sec is not None
            else max(0.0, float(file_dur or 0.0) - start_sec)
        )
    except RegionError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        logger.warning("Audio duration probe failed; timing estimates unavailable: %s", exc)
        job_audio_sec = float(max_duration_sec) if max_duration_sec is not None else None

    if job_requires_roformer_backend(choice["model"]) and not is_roformer_backend_available():
        st.error(f"RoFormer backend is not installed. {ROFORMER_INSTALL_HINT}")
        return

    try:
        ensure_cuda_available(choice["device"], get_desktop_probe())
    except RuntimeError:
        st.error(CUDA_UNAVAILABLE_MESSAGE)
        return

    resolved_name = output_name
    if region_label and max_duration_sec is not None:
        clip_suffix = format_region_label_filename(start_sec, float(max_duration_sec))
        resolved_name = f"{resolved_name}_{clip_suffix}"
        st.session_state["isolate_region_label"] = region_label
        st.session_state["isolate_clip_length"] = max_duration_sec
    else:
        st.session_state.pop("isolate_region_label", None)
        st.session_state.pop("isolate_clip_length", None)

    output_dir = run_output_dir()
    source_fp = st.session_state.get("isolate_pending_fp") or st.session_state.get("isolate_upload_fp")
    browser_id = st.session_state.get("isolate_user_id")
    source_kind = infer_source_kind(
        source_fingerprint=str(source_fp) if source_fp else None,
        youtube_url=choice.get("youtube_url"),
    )
    spec = IsolateJobSpec(
        id=uuid.uuid4().hex,
        audio_path=str(audio_path),
        output_dir=str(output_dir),
        title=resolved_name,
        model=choice["model"],
        quality=choice["quality"],
        device=choice["device"],
        start_sec=start_sec,
        max_duration_sec=max_duration_sec,
        two_stems=choice.get("two_stems"),
        guitar_checkpoint=choice.get("guitar_checkpoint"),
        two_pass=bool(choice.get("two_pass")),
        guitar_refine=bool(choice.get("guitar_refine")),
        low_end_restore_db=0.0,
        sub_bass_debleed=False,
        emit_stems=list(choice["emit_stems"]) if choice.get("emit_stems") else None,
        fold_other_into_guitar=bool(choice.get("fold_other_into_guitar", True)),
        fold_other_mode=str(choice.get("fold_other_mode") or "best_effort"),
        custom_stems=list(choice.get("custom_stems") or []),
        track_options=list(choice.get("track_options") or []),
        source_fingerprint=str(source_fp) if source_fp else None,
        source_kind=source_kind,
        region_label=region_label,
        owner=browser_id if isinstance(browser_id, str) else None,
        created_at=time.time(),
        audio_duration_sec=job_audio_sec,
        prior_timing=st.session_state.get("isolate_last_job_timing"),
    )
    st.session_state["isolate_last_custom_stems"] = list(choice.get("custom_stems") or [])
    st.session_state["isolate_results_source_fp"] = source_fp
    enqueue_job(spec)
    reset_new_tab_source(st.session_state)
    st.session_state["isolate_flash"] = f"Queued **{resolved_name}**."
    if job_audio_sec:
        st.session_state["isolate_last_job_timing"] = {
            "audio_sec": job_audio_sec,
            "quality": choice["quality"],
            "device": choice["device"],
            "model": choice["model"],
            "two_pass": bool(choice.get("two_pass")),
            "guitar_refine": bool(choice.get("guitar_refine")),
        }
    _open_queue_workspace()
    st.rerun()


def _library_status_row(row: dict) -> dict:
    return {
        "id": row.get("id") or row.get("run_dir"),
        "status": "succeeded",
        "title": row.get("title") or "tracks",
        "run_dir": row.get("run_dir"),
        "artifacts": row.get("artifacts") or {},
        "source_audio_path": row.get("source_audio_path"),
        "source_fingerprint": row.get("source_fingerprint"),
        "source_kind": row.get("source_kind"),
        "region_label": row.get("region_label"),
        "clip_length": row.get("clip_length"),
        "custom_stems": row.get("custom_stems") or [],
        "created_at": row.get("created_at"),
    }


def _apply_library_row(row: dict, *, viewing_mode: str, reopen_name: bool) -> bool:
    status = _library_status_row(row)
    if not apply_succeeded_job_to_session(
        st.session_state,
        status,
        viewing_mode=viewing_mode,
    ):
        return False
    run_dir = status.get("run_dir")
    if run_dir:
        st.session_state["isolate_listen_applied_dir"] = str(run_dir)
    if reopen_name:
        queue_reopen_output_name(st.session_state, status.get("title") or "tracks")
    _persist_isolate_ui_state()
    return True


def _library_rows_available(browser_id: str | None) -> list[dict]:
    owner = browser_id if isinstance(browser_id, str) else None
    owned = list_recent_runs("isolate", owner=owner)
    unfiltered = owned if owned else list_recent_runs("isolate")
    recent = recent_runs_with_owner_fallback(owned, unfiltered)
    merged = merge_library_runs(recent, list_jobs(limit=30))
    usable: list[dict] = []
    for row in merged:
        paths = _stem_paths_from_artifacts(row.get("artifacts") or {})
        if paths:
            usable.append(row)
    return usable


def _clear_loaded_mixer() -> None:
    for key in (
        "isolate_artifacts",
        "isolate_base_name",
        "isolate_run_dir",
        "isolate_volumes_db",
        "isolate_master_volume_db",
        "isolate_mixer_state",
        "isolate_mix_ready",
        "isolate_mix_fp",
        "isolate_selected_stems",
        "isolate_results_fp",
        "isolate_source_audio_path",
        "isolate_source_kind",
        "isolate_region_label",
        "isolate_clip_length",
        "isolate_viewing_run_dir",
        "isolate_listen_applied_dir",
        "isolate_listen_missing",
        "isolate_results_source_fp",
        "isolate_last_export_path",
        LISTEN_PICKER_KEY,
        LISTEN_PICKER_NEXT_KEY,
        "isolate_flash",
    ):
        st.session_state.pop(key, None)


def _apply_listen_pick(rows: list[dict]) -> None:
    """Apply a manual "Listening to" selection immediately in the widget callback.

    Deferred to the callback (rather than the main-body diff pass) so a concurrent
    rehydrate/poll pass cannot overwrite the user's choice with ``viewing_mode='latest'``
    before it is pinned.
    """
    chosen = st.session_state.get(LISTEN_PICKER_KEY)
    if not chosen:
        return
    row = next((r for r in rows if str(r.get("run_dir")) == str(chosen)), None)
    if row is None:
        st.session_state["isolate_listen_missing"] = str(chosen)
        return
    _apply_library_row(row, viewing_mode=str(row.get("id") or str(chosen)), reopen_name=True)


def _rename_listen_run() -> None:
    """Rename the currently-chosen mix from the editable "Listening to" name field.

    Runs only on Enter (on_change), so ordinary reruns never rewrite the title.
    """
    new_name = (st.session_state.get("isolate_listen_name") or "").strip()
    run_dir = st.session_state.get(LISTEN_PICKER_KEY) or st.session_state.get(
        "isolate_listen_applied_dir"
    )
    if not new_name or not run_dir:
        return
    current = st.session_state.get("isolate_base_name") or ""
    if new_name == current:
        return
    if rename_run_title(Path(run_dir), new_name):
        st.session_state["isolate_base_name"] = new_name
        _persist_isolate_ui_state()


def _render_listening_switcher(browser_id: str | None, rows: list[dict] | None = None) -> None:
    """Mixer library: selectbox of finished runs + delete current."""
    if rows is None:
        rows = _library_rows_available(browser_id)
    if not rows:
        return
    labels = {
        str(r["run_dir"]): format_source_title(
            r.get("title") or "tracks",
            infer_source_kind(
                source_kind=r.get("source_kind"),
                source_fingerprint=r.get("source_fingerprint"),
            ),
        )
        for r in rows
    }
    options = [str(r["run_dir"]) for r in rows]
    apply_listen_picker_pending(st.session_state)
    loaded = st.session_state.get("isolate_run_dir") or st.session_state.get(
        "isolate_listen_applied_dir"
    )
    current = st.session_state.get(LISTEN_PICKER_KEY)
    if current not in options:
        default = listen_picker_default(
            options,
            str(loaded) if loaded else None,
            None,
        )
        if default:
            st.session_state[LISTEN_PICKER_KEY] = default
    cols = st.columns([4, 1], vertical_alignment="bottom")
    with cols[0]:
        chosen = st.selectbox(
            "Listening to",
            options=options,
            format_func=lambda d: labels.get(d, d),
            key=LISTEN_PICKER_KEY,
            on_change=_apply_listen_pick,
            args=(rows,),
        )
    with cols[1]:
        delete_clicked = st.button(
            "Delete this run",
            key="isolate_delete_listening",
            width="stretch",
        )
    if delete_clicked and chosen:
        deleted = delete_library_run(chosen)
        if deleted:
            if st.session_state.get("isolate_run_dir") == chosen:
                _clear_loaded_mixer()
            st.session_state.pop("isolate_listen_applied_dir", None)
            st.session_state.pop(LISTEN_PICKER_KEY, None)
            st.session_state.pop(LISTEN_PICKER_NEXT_KEY, None)
            _persist_isolate_ui_state()
            st.rerun()
        else:
            st.error("Could not delete that separation.")
            return
    applied = st.session_state.get("isolate_listen_applied_dir")
    if chosen and chosen != applied:
        row = next((r for r in rows if str(r.get("run_dir")) == chosen), None)
        if row is None:
            st.caption("Those files are no longer available.")
            st.session_state["isolate_listen_missing"] = str(chosen)
            st.session_state.pop(LISTEN_PICKER_KEY, None)
            st.rerun()
            return
        viewing_id = str(row.get("id") or chosen)
        if _apply_library_row(row, viewing_mode=viewing_id, reopen_name=True):
            st.rerun()
        else:
            st.caption("Those files are no longer available.")
            st.session_state["isolate_listen_missing"] = str(chosen)
            st.session_state.pop(LISTEN_PICKER_KEY, None)
            st.rerun()

    rename_dir = chosen or st.session_state.get("isolate_listen_applied_dir")
    if rename_dir:
        current_name = st.session_state.get("isolate_base_name") or "tracks"
        if st.session_state.get("isolate_listen_name_for") != rename_dir:
            st.session_state["isolate_listen_name"] = current_name
            st.session_state["isolate_listen_name_for"] = rename_dir
        st.text_input(
            label="Mix name",
            value=current_name,
            key="isolate_listen_name",
            on_change=_rename_listen_run,
        )


def _has_source_for_job(choice: dict) -> bool:
    uploaded = choice.get("uploaded")
    return bool(
        uploaded
        or choice.get("youtube_url")
        or (
            st.session_state.get("carry_over_audio_path")
            and Path(st.session_state["carry_over_audio_path"]).exists()
        )
        or (
            st.session_state.get("isolate_pending_audio_path")
            and Path(st.session_state["isolate_pending_audio_path"]).exists()
        )
    )


def _render_new_workspace(demucs_ok: bool) -> None:
    choice = _render_separation_controls()
    if st.button(
        "Separate tracks",
        type="primary",
        disabled=not demucs_ok,
        key="isolate_separate",
    ):
        if choice.get("error"):
            st.error(choice["error"])
        elif choice.get("max_duration_sec") is not None and choice["max_duration_sec"] < MIN_REGION_SEC:
            st.error(f"Section must be at least {MIN_REGION_SEC:.0f} seconds.")
        elif not _has_source_for_job(choice):
            st.error("Upload an audio file or enter a YouTube URL.")
        else:
            audio_path, resolve_error = _resolve_audio_for_job(choice)
            if resolve_error:
                st.error(resolve_error)
            elif audio_path is None:
                st.error("Upload an audio file or enter a YouTube URL.")
            else:
                _enqueue_confirmed_job(choice, audio_path)


def _render_mixer_region_caption(base_name: str) -> None:
    region_caption = st.session_state.get("isolate_region_label")
    source_audio_path = st.session_state.get("isolate_source_audio_path")
    clip_length = st.session_state.get("isolate_clip_length")
    filename = Path(source_audio_path).name if source_audio_path else None
    kind = infer_source_kind(
        source_kind=st.session_state.get("isolate_source_kind"),
        source_fingerprint=st.session_state.get("isolate_results_source_fp"),
    )
    st.caption(
        format_source_caption(
            base_name,
            kind,
            filename=filename,
            region_label=region_caption if isinstance(region_caption, str) else None,
            clip_length=float(clip_length) if clip_length is not None else None,
        )
    )


def _load_parent_config(run_dir: Path) -> dict:
    """Read the parent run's persisted separator config (Feature 2), else {}."""
    meta_path = run_dir / "meta.json"
    if not meta_path.is_file():
        return {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    cfg = meta.get("config")
    return dict(cfg) if isinstance(cfg, dict) else {}


def _enqueue_reseparate_job(
    stem_id: str,
    stem_path: Path,
    run_dir: Path,
    parent_config: dict,
) -> None:
    """Enqueue a re-separate of one existing stem, defaulting from the parent run."""
    output_dir = run_output_dir()
    source_fp = st.session_state.get("isolate_results_source_fp")
    source_kind = infer_source_kind(
        source_fingerprint=str(source_fp) if source_fp else None,
        source_kind=st.session_state.get("isolate_source_kind"),
    )
    spec = IsolateJobSpec(
        id=uuid.uuid4().hex,
        audio_path=str(stem_path),
        output_dir=str(output_dir),
        title=f"{stem_id} (re-separate)",
        model=str(parent_config.get("model") or "htdemucs_6s"),
        quality=str(parent_config.get("quality") or "balanced"),
        device=str(parent_config.get("device") or "cpu"),
        two_pass=bool(parent_config.get("two_pass", False)),
        guitar_refine=bool(parent_config.get("guitar_refine", False)),
        low_end_restore_db=float(parent_config.get("low_end_restore_db") or 0.0),
        sub_bass_debleed=bool(parent_config.get("sub_bass_debleed", False)),
        # Fold-other is off by default for a breakdown.
        fold_other_into_guitar=False,
        fold_other_mode="best_effort",
        custom_stems=[stem_id],
        source_fingerprint=str(source_fp) if source_fp else None,
        source_kind=source_kind,
        owner=st.session_state.get("isolate_user_id"),
        created_at=time.time(),
        reseparate_from=stem_id,
        parent_run_dir=str(run_dir),
    )
    enqueue_job(spec)
    st.session_state["isolate_flash"] = f"Queued breakdown of **{stem_id}**."
    _open_queue_workspace()
    st.rerun()


def _render_reseparate_panel(stem_paths: dict[str, Path], run_dir: Path) -> None:
    """'Break down a stem' control — re-separate one stem in place (section 6)."""
    if len(stem_paths) < 1:
        return
    parent_config = _load_parent_config(run_dir)
    run_fp = hashlib.sha256(str(run_dir.resolve()).encode()).hexdigest()[:12]
    with st.expander(
        "Break down a stem (re-separate)",
        expanded=False,
    ):
        st.caption(
            "Re-run the separator on one existing stem to break out more "
            "instruments without reprocessing the whole track. On success the "
            "source stem is replaced in the mixer by its new sub-stems."
        )
        if not parent_config:
            st.caption("Parent run has no saved separator config — using defaults.")
        for stem_id in sort_stem_names(stem_paths.keys()):
            label = stem_label_for_id(stem_id)
            if st.button(
                f"Break down {label}",
                key=f"reseparate_{run_fp}_{stem_id}",
                help=f"Separate `{stem_id}` again into sub-stems.",
            ):
                _enqueue_reseparate_job(stem_id, stem_paths[stem_id], run_dir, parent_config)


def _render_mixer_workspace(browser_id: str | None) -> None:
    owner = browser_id if isinstance(browser_id, str) else None
    rows = _library_rows_available(owner)
    if not _session_has_mixer_wavs():
        row = select_rehydrate_row(st.session_state, rows, wav_exists=_wav_exists)
        if row is not None and _apply_library_row(
            row, viewing_mode="latest", reopen_name=False
        ):
            st.rerun()

    if rows:
        _render_listening_switcher(owner, rows)

    artifacts_map = st.session_state.get("isolate_artifacts")
    stem_paths = _stem_paths_from_artifacts(artifacts_map or {})
    if not stem_paths:
        if not rows:
            st.caption("No tracks yet.")
        else:
            st.caption("Pick a run above.")
        return

    pending_fp = pending_upload_fp_for_stale(st.session_state)
    show_file_ready_banner = should_hide_stale_results(
        pending_upload_fp=pending_fp,
        has_artifacts=True,
        results_source_fp=st.session_state.get("isolate_results_source_fp"),
    )
    if not show_file_ready_banner:
        st.caption(
            "New file selected — mixer is still the chosen run until you separate again."
        )

    base_name = st.session_state.get("isolate_base_name", "stems")
    st.session_state["isolate_results_fp"] = _artifact_fingerprint(stem_paths)
    run_dir = Path(
        st.session_state.get("isolate_run_dir", next(iter(stem_paths.values())).parent)
    )

    bass_bleed = _load_bass_bleed_diagnostics(artifacts_map)
    if bass_bleed.get("flagged"):
        st.warning(
            "Guitar check: "
            f"{bass_bleed.get('reason', 'this track may contain extra bass bleed')} "
            "Use **Guitar fix-up** below to adjust without re-separating."
        )

    _render_guitar_fixup_panel(stem_paths, run_dir, artifacts_map or {}, bass_bleed)

    _render_reseparate_panel(stem_paths, run_dir)

    _render_mixer_region_caption(base_name)

    # NOTE: media URLs are generated once per session state, but Streamlit fragments
    # may re-render at different times. If URL generation becomes expensive or stale,
    # wrap with @st.cache_resource and a TTL.
    mixer_media_urls, mixer_download_urls = register_mixer_media(stem_paths)
    _mixer_and_downloads_fragment(
        stem_paths,
        base_name=base_name,
        run_dir=run_dir,
        media_urls=mixer_media_urls,
        download_urls=mixer_download_urls,
    )

    source_audio_path = st.session_state.get("isolate_source_audio_path")
    if source_audio_path and Path(source_audio_path).exists():
        st.divider()
        st.caption("Other tools")
        if st.button("Make a tab PDF from this →"):
            st.session_state["carry_over_audio_path"] = source_audio_path
            st.session_state["carry_over_audio_name"] = Path(source_audio_path).name
            _request_loading_overlay()
            st.switch_page(str(Path(__file__).with_name("tab_pdf.py")))


def _render_file_ready_banner() -> None:
    pending_fp = pending_upload_fp_for_stale(st.session_state)
    if not should_hide_stale_results(
        pending_upload_fp=pending_fp,
        has_artifacts=bool(st.session_state.get("isolate_artifacts")),
        results_source_fp=st.session_state.get("isolate_results_source_fp"),
    ):
        return
    st.info(
        f"**{_staged_source_name()}** is ready — click **Separate tracks** on New to "
        "replace the current results. Existing stems stay on disk until the new job finishes."
    )


def main() -> None:
    title_col, refresh_col = st.columns([6, 1], vertical_alignment="center")
    with title_col:
        st.title("Audio Isolation")
    with refresh_col:
        refresh_clicked = st.button(
            "Refresh",
            key="isolate_refresh",
            help="Re-scan the local run library",
            width="stretch",
        )

    if not shutil.which("ffmpeg"):
        st.error(
            "ffmpeg is required for audio conversion but was not found on PATH. "
            f"{_ffmpeg_install_hint()}"
        )
        return

    demucs_ok = is_demucs_available()
    if not demucs_ok:
        st.error(
            "Audio separation requires Demucs, which is not installed. "
            f"{DEMUCS_INSTALL_HINT}"
        )
        return

    logger.debug("isolate paint demucs=%s", demucs_ok)
    ensure_worker_started()
    browser_id = _get_browser_user_id()
    _restore_isolate_ui_state()
    if refresh_clicked:
        _refresh_isolate_from_disk(browser_id)
    _rehydrate_artifacts_from_disk(browser_id)

    prev_workspace = st.session_state.get(WORKSPACE_KEY)
    _ensure_workspace_tab(has_artifacts=bool(st.session_state.get("isolate_artifacts")))
    cur_workspace = st.session_state.get(WORKSPACE_KEY)

    # Only show the global loading overlay for a page/tab switch or while a
    # separation job is actually running — never for ordinary button reruns.
    _update_global_loading_flag(
        job_running=_worker_jobs_active(),
        tab_changed=(
            prev_workspace in WORKSPACE_TABS
            and cur_workspace in WORKSPACE_TABS
            and prev_workspace != cur_workspace
        ),
        nav_requested=bool(st.session_state.pop("_nav_loading", False)),
    )

    _poll_running_jobs()
    if flash := st.session_state.pop("isolate_flash", None):
        st.success(flash)
    _render_file_ready_banner()

    tab_new, tab_mixer, tab_queue = st.tabs(
        list(WORKSPACE_TABS),
        key=WORKSPACE_KEY,
        on_change="rerun",
    )
    selected = st.session_state.get(WORKSPACE_KEY, "New")
    if selected not in WORKSPACE_TABS:
        selected = "New"
    with tab_new:
        try:
            _render_new_workspace(demucs_ok)
        except Exception as exc:
            logger.exception("New tab failed to draw")
            st.error("Could not draw the new tab. Try clicking Refresh, or check that the file is valid audio.")
            with st.expander("Technical details"):
                st.exception(exc)
    with tab_mixer:
        if selected == "Mixer":
            _render_mixer_workspace(browser_id if isinstance(browser_id, str) else None)
    with tab_queue:
        _queue_tab_fragment()

    st.session_state["_isolate_form_drawn"] = True
    _persist_isolate_ui_state()


if __name__ == "__main__":
    main()
