"""Streamlit page: Audio Isolation — separate songs into instrument tracks."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import threading
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st
from streamlit_local_storage import LocalStorage

from ui.common import (
    AUDIO_UPLOAD_TYPES,
    delete_run,
    ensure_src_path,
    list_recent_runs,
    run_output_dir,
    save_upload,
    write_run_metadata,
)
from ui.isolate_state import (
    CUSTOM_STEM_CHOICES,
    DEFAULT_CUSTOM_STEMS,
    DEFAULT_SEPARATION_PRESET,
    DEFAULT_SPEED_PRESET,
    ISOLATION_STAGE_ORDER,
    SEPARATION_PRESETS,
    SPEED_PRESETS,
    clamp_region_bounds,
    custom_selected_stems,
    default_region_end,
    format_elapsed,
    format_progress_label,
    resolve_custom_separation,
    resolve_separation_preset,
    resolve_speed_preset,
    should_hide_stale_results,
    stage_progress_percent,
    sync_output_name_on_upload,
    upload_fingerprint,
)
from ui.media import cleanup_mix_artifacts, ensure_mixer_audio_paths, stem_media_urls
from ui.stem_mixer_component import component_build_available, stem_mixer

ensure_src_path()

from audio_to_tab.isolate import (  # noqa: E402
    DEMUCS_INSTALL_HINT,
    IsolateConfig,
    MIN_REGION_SEC,
    RegionError,
    format_region_label,
    format_region_label_filename,
    format_time_sec,
    probe_duration_sec,
    resolve_region,
    separate_stems,
)
from audio_to_tab.mixer import (  # noqa: E402
    DB_DEFAULT,
    effective_linear_gains,
    mix_stems_to_wav,
    sort_stem_names,
    stem_display_name,
    waveform_peaks,
)
from audio_to_tab.separate import is_demucs_available  # noqa: E402

STEM_HINTS = {
    "piano": "May sound less accurate than other tracks",
    "lead_guitar": "Created from the Guitar track (best effort)",
    "rhythm_guitar": "Created from the Guitar track (best effort)",
    "guitar1": "Legacy spatial label",
    "guitar2": "Legacy spatial label",
}

_LS_USER_ID_KEY = "isolate_user_id"
_LS_COMPONENT_KEY = "isolate_local_storage"


def _stateful_expander(label: str, *, key: str, default: bool = False):
    """
    Expander that remembers whether the user left it open.

    The live mixer reruns the page on every interaction. Without a key the
    expander would snap back to ``default`` each time; with one, Streamlit
    tracks the open state in ``st.session_state[key]``. ``default`` and
    ``label`` must stay constant across reruns or the widget identity changes
    and the state is lost.
    """
    return st.expander(label, expanded=default, key=key, on_change="rerun")


def _get_browser_user_id() -> str:
    """
    Persistent anonymous id for this browser (localStorage), cached in session_state.

    The LocalStorage component often returns an empty dict on the first script run
    before browser data arrives, so we hydrate once before minting a new id.
    """
    cached = st.session_state.get("isolate_user_id")
    if isinstance(cached, str) and cached:
        return cached

    local_s = LocalStorage(key=_LS_COMPONENT_KEY)
    stored_items = st.session_state.get(_LS_COMPONENT_KEY)
    if isinstance(stored_items, dict):
        local_s.storedItems = stored_items
    else:
        stored_items = local_s.getAll() or {}

    stored = None
    if isinstance(stored_items, dict):
        stored = stored_items.get(_LS_USER_ID_KEY)
    if not stored:
        stored = local_s.getItem(_LS_USER_ID_KEY)

    if isinstance(stored, str) and stored.strip():
        user_id = stored.strip()
        st.session_state["isolate_user_id"] = user_id
        return user_id

    # First empty observation: wait briefly for the component to report browser state,
    # then rerun once before minting so we don't overwrite an existing id.
    if not st.session_state.get("_isolate_user_id_hydrated"):
        st.session_state["_isolate_user_id_hydrated"] = True
        time.sleep(0.5)
        stored_items = st.session_state.get(_LS_COMPONENT_KEY) or {}
        if isinstance(stored_items, dict):
            local_s.storedItems = stored_items
            stored = stored_items.get(_LS_USER_ID_KEY) or local_s.getItem(_LS_USER_ID_KEY)
            if isinstance(stored, str) and stored.strip():
                user_id = stored.strip()
                st.session_state["isolate_user_id"] = user_id
                return user_id
        st.rerun()

    user_id = uuid.uuid4().hex
    local_s.setItem(_LS_USER_ID_KEY, user_id, key="isolate_set_user_id")
    st.session_state["isolate_user_id"] = user_id
    return user_id


def _stem_waveform_peaks(path: Path, *, num_points: int = 80) -> list[float]:
    try:
        return waveform_peaks(path, num_points=num_points).tolist()
    except Exception:
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


def _increment_upload_key() -> None:
    st.session_state["isolate_upload_key"] = st.session_state.get("isolate_upload_key", 0) + 1
    st.session_state.pop("isolate_upload_fp", None)


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


def _load_stem_presence(artifacts: dict) -> dict:
    path = artifacts.get("stem_presence_diagnostics")
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_bass_bleed_diagnostics(artifacts: dict) -> dict:
    path = artifacts.get("bass_bleed_diagnostics")
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_guitar_split_diagnostics(artifacts: dict) -> dict:
    path = artifacts.get("guitar_split_diagnostics")
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def default_isolate_selected_stems(
    produced_stem_names: list[str],
    presence: dict,
) -> dict[str, bool]:
    """
    Initial Detected Instruments checkbox state.

    Lead Guitar and Rhythm Guitar are always checked when present.
    Combined Guitar is unchecked when both derived stems exist.
    """
    selected = {
        name: bool(presence.get(name, {}).get("present", True))
        for name in produced_stem_names
    }
    for name in ("lead_guitar", "rhythm_guitar"):
        if name in selected:
            selected[name] = True
    if "lead_guitar" in selected and "rhythm_guitar" in selected:
        if "guitar" in selected:
            selected["guitar"] = False
    return selected


def _render_stem_presence_selector(
    stem_paths: dict[str, Path],
    presence: dict,
    fingerprint: str,
) -> None:
    selected = st.session_state.setdefault("isolate_selected_stems", {})
    stem_names = sort_stem_names(stem_paths.keys())
    cols_per_row = 3
    for row_start in range(0, len(stem_names), cols_per_row):
        row_names = stem_names[row_start : row_start + cols_per_row]
        cols = st.columns(len(row_names))
        for col, name in zip(cols, row_names):
            with col:
                label = stem_display_name(name)
                info = presence.get(name)
                if not info:
                    help_text = "No detection data available for this track."
                elif info.get("present", True):
                    help_text = f"Detected — mean level {info.get('mean_dbfs', 0.0):.1f} dBFS"
                else:
                    help_text = (
                        f"Not detected — mean level {info.get('mean_dbfs', 0.0):.1f} dBFS, "
                        "but you can still include it"
                    )
                checked = st.checkbox(
                    label,
                    value=selected.get(name, True),
                    key=f"select_stem_{fingerprint}_{name}",
                    help=help_text,
                )
                selected[name] = checked


def _cached_zip_bytes(
    stem_paths: dict[str, Path],
    base_name: str,
    run_dir: Path,
) -> bytes:
    """Build zip only when the selected-stem set changes (cached on disk)."""
    fingerprint = _selection_fingerprint(stem_paths)
    zip_name = f"{base_name}_stems.zip"
    zip_path = run_dir / zip_name
    cache_key = st.session_state.get("isolate_zip_fp")
    if cache_key == fingerprint and zip_path.is_file():
        return zip_path.read_bytes()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, path in sorted(stem_paths.items()):
            zf.writestr(f"{name}.wav", path.read_bytes())
    data = buf.getvalue()
    zip_path.write_bytes(data)
    st.session_state["isolate_zip_fp"] = fingerprint
    st.session_state["isolate_zip_name"] = zip_name
    return data


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


_ISOLATION_STAGE_DISPLAY = {
    "ingest": "Preparing audio…",
    "separate": "Separating tracks… this can take a while on CPU",
    "collect": "Collecting tracks…",
    "bass_bleed": "Checking guitar…",
    "guitar_split": "Splitting lead / rhythm guitar…",
    "presence": "Checking which tracks have sound…",
    "done": "Finishing…",
}


def _render_live_mixer(
    stem_paths: dict[str, Path], *, track_title: str = "", base_name: str = "stems"
) -> dict | None:
    if not component_build_available():
        st.error(
            "Live mixer is not built. "
            "Run: npm install && npm run build in ui/stem_mixer_component/frontend "
            "(or .\\scripts\\dev.ps1 mixer-build)."
        )
        return None

    mixer_paths = ensure_mixer_audio_paths(stem_paths)
    if mixer_paths != stem_paths:
        st.caption(
            "Using lighter preview audio for playback. Downloads still use the full-quality files."
        )

    try:
        urls = stem_media_urls(mixer_paths)
        # Registered separately (full-quality originals) so per-track downloads inside
        # the mixer are never the downsampled browser-preview audio.
        download_urls = stem_media_urls(stem_paths, coord_prefix="isolate.download")
    except Exception as exc:
        st.error(f"Could not prepare track audio for the mixer: {exc}")
        return None

    stem_names = sort_stem_names(stem_paths.keys())
    volumes = st.session_state.setdefault("isolate_volumes_db", {})
    for name in stem_names:
        volumes.setdefault(name, DB_DEFAULT)
    master_db = float(st.session_state.setdefault("isolate_master_volume_db", DB_DEFAULT))

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
    fingerprint = _artifact_fingerprint(stem_paths)
    return stem_mixer(
        stems_arg,
        initial_volumes_db={n: float(volumes.get(n, DB_DEFAULT)) for n in stem_names},
        initial_muted={n: False for n in stem_names},
        initial_soloed={n: False for n in stem_names},
        initial_master_volume_db=master_db,
        track_title=track_title,
        key=f"stem_mixer_{fingerprint}",
    )


def _preset_radio_label(preset_id: str) -> str:
    preset = SEPARATION_PRESETS[preset_id]
    count = preset.get("track_count")
    if count is None:
        return f"{preset['label']} — {preset['tracks']}"
    return f"{preset['label']} — {preset['tracks']} ({count} tracks)"


def _speed_preset_radio_label(preset_id: str) -> str:
    return SPEED_PRESETS[preset_id]["label"]


def _ensure_pending_audio(uploaded: object) -> Path | None:
    """Save upload to disk when fingerprint changes so duration/preview work."""
    fp = upload_fingerprint(uploaded)
    if fp is None:
        return None
    last_fp = st.session_state.get("isolate_upload_fp")
    pending = st.session_state.get("isolate_pending_audio_path")
    if fp == last_fp and pending and Path(pending).exists():
        return Path(pending)
    if uploaded is not None:
        path = save_upload(uploaded)
        st.session_state["isolate_pending_audio_path"] = str(path)
        return path
    return None


def _active_source_path(uploaded: object) -> Path | None:
    pending = st.session_state.get("isolate_pending_audio_path")
    if pending and Path(pending).exists():
        return Path(pending)
    carry = st.session_state.get("carry_over_audio_path")
    if not uploaded and carry and Path(carry).exists():
        return Path(carry)
    return None


def _render_region_controls(audio_path: Path | None) -> tuple[float, float | None, str | None]:
    """
    Region UI on the main path. Returns (start_sec, max_duration_sec, region_label).

    ``max_duration_sec`` is None for full-file processing.
    """
    if audio_path is None or not audio_path.exists():
        return 0.0, None, None

    duration = probe_duration_sec(audio_path)
    if duration is None:
        st.caption("Length: unknown — full file will be processed.")
        return 0.0, None, None

    st.caption(f"Length: **{format_time_sec(duration)}** ({duration:.1f} s)")

    use_region = st.checkbox(
        "Isolate only a section",
        value=st.session_state.get("isolate_use_region", False),
        key="isolate_use_region",
        help="Off = process the entire file. On = pick start and end times.",
    )

    if not use_region:
        st.audio(str(audio_path))
        return 0.0, None, None

    default_end = default_region_end(duration)
    region_key = f"isolate_region_{st.session_state.get('isolate_upload_fp', 'none')}"
    if region_key not in st.session_state:
        st.session_state[region_key] = (0.0, default_end)

    start_default, end_default = st.session_state[region_key]
    start_default, end_default = clamp_region_bounds(
        start_default, end_default, duration, min_length=MIN_REGION_SEC
    )

    start_sec, end_sec = st.slider(
        "Section (start → end)",
        min_value=0.0,
        max_value=float(duration),
        value=(float(start_default), float(end_default)),
        step=1.0,
        key=f"{region_key}_slider",
    )
    start_sec, end_sec = clamp_region_bounds(
        start_sec, end_sec, duration, min_length=MIN_REGION_SEC
    )
    st.session_state[region_key] = (start_sec, end_sec)

    length = end_sec - start_sec
    region_label = format_region_label(start_sec, length)
    st.caption(f"**{region_label}** ({length:.0f} s)")

    try:
        audio_bytes = audio_path.read_bytes()
        st.audio(
            audio_bytes,
            format="audio/wav" if audio_path.suffix.lower() == ".wav" else None,
            start_time=int(start_sec),
            end_time=int(end_sec),
        )
    except Exception:
        st.audio(str(audio_path))

    if length < MIN_REGION_SEC:
        st.error(f"Section must be at least {MIN_REGION_SEC:.0f} seconds.")
        return start_sec, None, region_label

    return start_sec, length, region_label


def _render_separation_controls() -> dict:
    """Track choice, upload, region, speed preset; quality/device/name in advanced."""
    if "isolate_separation_preset" not in st.session_state:
        st.session_state["isolate_separation_preset"] = DEFAULT_SEPARATION_PRESET
    if "isolate_speed_preset" not in st.session_state:
        st.session_state["isolate_speed_preset"] = DEFAULT_SPEED_PRESET

    st.subheader("What to separate")
    preset_id = st.radio(
        "Tracks",
        options=list(SEPARATION_PRESETS.keys()),
        format_func=_preset_radio_label,
        key="isolate_separation_preset",
        label_visibility="collapsed",
    )

    custom_stems: list[str] = []
    preset_error: str | None = None
    if preset_id == "custom":
        cols = st.columns(3)
        for idx, (stem_id, label) in enumerate(CUSTOM_STEM_CHOICES.items()):
            with cols[idx % 3]:
                # value= only seeds the first render; the key keeps the user's
                # choice across the reruns the mixer and uploader trigger.
                checked = st.checkbox(
                    label,
                    value=stem_id in DEFAULT_CUSTOM_STEMS,
                    key=f"isolate_custom_{stem_id}",
                )
                if checked:
                    custom_stems.append(stem_id)
        try:
            resolved = resolve_custom_separation(custom_stems)
        except ValueError as exc:
            preset_error = str(exc)
            st.warning(preset_error)
            resolved = resolve_separation_preset("custom")
    else:
        resolved = resolve_separation_preset(preset_id)
    if resolved["caveat"]:
        st.caption(resolved["caveat"])

    uploaded = st.file_uploader(
        "Upload MP3 / WAV / FLAC / M4A",
        type=AUDIO_UPLOAD_TYPES,
        key=f"isolate_upload_{st.session_state.get('isolate_upload_key', 0)}",
    )
    _sync_upload_output_name(uploaded)
    if uploaded is not None:
        _ensure_pending_audio(uploaded)

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
    start_sec, max_duration_sec, region_label = _render_region_controls(audio_path)

    st.subheader("Processing speed")
    speed_id = st.radio(
        "Speed",
        options=list(SPEED_PRESETS.keys()),
        format_func=_speed_preset_radio_label,
        key="isolate_speed_preset",
        label_visibility="collapsed",
        horizontal=True,
    )
    speed = resolve_speed_preset(speed_id)
    if speed["help"]:
        st.caption(speed["help"])

    # The speed preset drives Quality/Device; an advanced override sticks until the
    # user picks a different speed.
    if st.session_state.get("isolate_speed_applied") != speed["id"]:
        st.session_state["isolate_speed_applied"] = speed["id"]
        st.session_state["isolate_quality"] = speed["quality"]
        st.session_state["isolate_device"] = speed["device"]

    with _stateful_expander(
        "Advanced options", key="isolate_options_expanded", default=True
    ):
        quality = st.selectbox(
            "Quality",
            options=["fast", "balanced", "high", "extreme"],
            help="Higher quality is slower, especially on CPU.",
            key="isolate_quality",
        )
        device = st.selectbox(
            "Device",
            options=["cpu", "cuda"],
            key="isolate_device",
        )
        st.text_input(
            "Output name",
            help="Used for downloaded file names. Defaults to the uploaded file's name.",
            key="isolate_output_name",
        )

    output_name = st.session_state.get("isolate_output_name", default_name or "")
    return {
        "model": resolved["model"],
        "two_stems": resolved["two_stems"],
        "custom_stems": custom_stems,
        "error": preset_error,
        "quality": quality,
        "device": device,
        "start_sec": start_sec,
        "max_duration_sec": max_duration_sec,
        "uploaded": uploaded,
        "output_name": output_name,
        "region_label": region_label,
    }


def _ffmpeg_install_hint() -> str:
    if sys.platform == "darwin":
        return "Install ffmpeg: brew install ffmpeg"
    if sys.platform.startswith("win"):
        return "Install ffmpeg: winget install Gyan.FFmpeg (full/shared build, not essentials-only)"
    return "Install ffmpeg: sudo apt install ffmpeg (or your distro equivalent)"


def main() -> None:
    st.title("Audio Isolation")

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

    has_results = bool(st.session_state.get("isolate_artifacts"))
    browser_id = _get_browser_user_id()

    choice = _render_separation_controls()
    uploaded = choice["uploaded"]
    start_sec = choice["start_sec"]
    max_duration_sec = choice["max_duration_sec"]
    region_label = choice["region_label"]
    output_name = choice["output_name"]

    pending_new_upload = uploaded is not None
    pending_upload_fp = st.session_state.get("isolate_upload_fp")
    if should_hide_stale_results(
        pending_upload_fp=pending_upload_fp,
        has_artifacts=has_results,
    ):
        upload_name = uploaded.name if uploaded else "New file"
        st.info(
            f"**{upload_name}** is ready — click **Separate tracks** to replace the "
            "current results."
        )

    recent_runs = list_recent_runs("isolate", owner=browser_id)
    if recent_runs:
        with _stateful_expander(
            "Recent separations", key="isolate_recent_expanded", default=False
        ):
            if pending_new_upload:
                st.caption(
                    "Finish or clear your new upload before reopening a past separation."
                )
            for run in recent_runs:
                run_artifacts = run.get("artifacts", {})
                available = bool(run_artifacts) and all(
                    Path(p).exists()
                    for name, p in run_artifacts.items()
                    if Path(p).suffix.lower() == ".wav"
                )
                cols = st.columns([3, 1, 1])
                with cols[0]:
                    created_at = run.get("created_at")
                    when = (
                        datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M")
                        if created_at
                        else ""
                    )
                    st.write(run.get("title") or "tracks")
                    st.caption(when if available else f"{when} — files no longer available")
                with cols[1]:
                    if available and st.button(
                        "Reopen",
                        key=f"reopen_isolate_{run['run_dir']}",
                        disabled=pending_new_upload,
                    ):
                        presence = _load_stem_presence(run_artifacts)
                        produced_stem_names = [
                            name
                            for name, path in run_artifacts.items()
                            if name
                            not in (
                                "guitar_split_diagnostics",
                                "stem_presence_diagnostics",
                                "bass_bleed_diagnostics",
                            )
                            and Path(path).suffix.lower() == ".wav"
                        ]
                        st.session_state["isolate_artifacts"] = run_artifacts
                        title = run.get("title") or "tracks"
                        st.session_state["isolate_base_name"] = title
                        st.session_state["isolate_run_dir"] = run["run_dir"]
                        st.session_state["isolate_output_name"] = title
                        st.session_state.pop("isolate_volumes_db", None)
                        st.session_state.pop("isolate_master_volume_db", None)
                        st.session_state.pop("isolate_mixer_state", None)
                        st.session_state.pop("isolate_mix_ready", None)
                        st.session_state.pop("isolate_mix_fp", None)
                        st.session_state.pop("isolate_zip_fp", None)
                        st.session_state["isolate_selected_stems"] = (
                            default_isolate_selected_stems(produced_stem_names, presence)
                        )
                        st.session_state.pop("isolate_flash", None)
                        st.session_state.pop("isolate_source_audio_path", None)
                        _increment_upload_key()
                        reopened_paths = _stem_paths_from_artifacts(run_artifacts)
                        if reopened_paths:
                            st.session_state["isolate_results_fp"] = _artifact_fingerprint(
                                reopened_paths
                            )
                        st.rerun()
                with cols[2]:
                    if st.button(
                        "Delete",
                        key=f"delete_isolate_{run['run_dir']}",
                        disabled=pending_new_upload,
                    ):
                        # Keep "Recent separations" open across the rerun below so the
                        # user doesn't lose their place.
                        st.session_state["isolate_recent_expanded"] = True
                        deleted = delete_run(run["run_dir"])
                        if deleted:
                            if st.session_state.get("isolate_run_dir") == run["run_dir"]:
                                for key in (
                                    "isolate_artifacts",
                                    "isolate_base_name",
                                    "isolate_run_dir",
                                    "isolate_volumes_db",
                                    "isolate_master_volume_db",
                                    "isolate_mixer_state",
                                    "isolate_mix_ready",
                                    "isolate_mix_fp",
                                    "isolate_zip_fp",
                                    "isolate_selected_stems",
                                    "isolate_results_fp",
                                    "isolate_source_audio_path",
                                    "isolate_flash",
                                ):
                                    st.session_state.pop(key, None)
                            st.rerun()
                        else:
                            st.error("Could not delete that separation.")

    run_separate = st.button(
        "Separate tracks",
        type="primary",
        disabled=not demucs_ok,
        key="isolate_separate",
    )

    if run_separate:
        if choice["error"]:
            st.error(choice["error"])
            return

        carry_over_path = st.session_state.get("carry_over_audio_path")
        using_carry_over = bool(
            not uploaded and carry_over_path and Path(carry_over_path).exists()
        )
        if not uploaded and not using_carry_over:
            st.error("Upload an audio file.")
            return

        if max_duration_sec is not None and max_duration_sec < MIN_REGION_SEC:
            st.error(f"Section must be at least {MIN_REGION_SEC:.0f} seconds.")
            return

        output_dir = run_output_dir()
        config = IsolateConfig(
            model=choice["model"],
            quality=choice["quality"],
            device=choice["device"],
            start_sec=start_sec,
            max_duration_sec=max_duration_sec,
            two_stems=choice["two_stems"],
        )

        separation_started = time.monotonic()

        try:
            pending = st.session_state.get("isolate_pending_audio_path")
            if uploaded and pending and Path(pending).exists():
                audio_path = Path(pending)
            elif uploaded:
                audio_path = save_upload(uploaded)
            else:
                audio_path = Path(carry_over_path)

            if max_duration_sec is not None:
                file_dur = probe_duration_sec(audio_path)
                try:
                    _, validated_length, _ = resolve_region(
                        file_dur,
                        start_sec,
                        start_sec + max_duration_sec,
                    )
                    config.max_duration_sec = validated_length
                except RegionError as exc:
                    st.error(str(exc))
                    return

            with st.status("Separating tracks…", expanded=True) as status:
                progress_bar = st.progress(0.0)
                progress_label = st.empty()
                elapsed_label = st.empty()

                progress_state: dict[str, str] = {
                    "stage": "ingest",
                    "message": "Preparing audio…",
                }
                result_holder: dict = {}

                def on_progress(stage: str, message: str) -> None:
                    progress_state["stage"] = stage
                    progress_state["message"] = message

                def paint_progress() -> None:
                    elapsed = format_elapsed(time.monotonic() - separation_started)
                    stage = progress_state["stage"]
                    message = progress_state["message"]
                    display = _ISOLATION_STAGE_DISPLAY.get(stage, message)
                    elapsed_label.markdown(f"**Elapsed:** `{elapsed}`")
                    if stage in ISOLATION_STAGE_ORDER:
                        pct = stage_progress_percent(stage)
                        progress_bar.progress(pct)
                        progress_label.caption(format_progress_label(pct, display))
                    status.update(label=f"{display} · {elapsed}")

                def worker() -> None:
                    try:
                        result_holder["artifacts"] = separate_stems(
                            audio_path=audio_path,
                            output_dir=output_dir,
                            config=config,
                            on_progress=on_progress,
                        )
                    except Exception as exc:  # noqa: BLE001 — re-raised on main thread
                        result_holder["error"] = exc

                thread = threading.Thread(target=worker, daemon=True)
                thread.start()
                paint_progress()
                while thread.is_alive():
                    time.sleep(0.25)
                    paint_progress()
                thread.join()
                paint_progress()

                if "error" in result_holder:
                    raise result_holder["error"]
                artifacts = result_holder["artifacts"]

            cleanup_mix_artifacts(output_dir)
            st.session_state["isolate_artifacts"] = {k: str(v) for k, v in artifacts.items()}
            stem_name = (
                Path(uploaded.name).stem
                if uploaded
                else (
                    Path(st.session_state.get("carry_over_audio_name") or "").stem
                    if using_carry_over
                    else audio_path.stem
                )
            )
            resolved_name = (output_name or "").strip() or stem_name
            if region_label and max_duration_sec is not None:
                clip_suffix = format_region_label_filename(start_sec, max_duration_sec)
                resolved_name = f"{resolved_name}_{clip_suffix}"
                st.session_state["isolate_region_label"] = region_label
                st.session_state["isolate_clip_length"] = max_duration_sec
            else:
                st.session_state.pop("isolate_region_label", None)
                st.session_state.pop("isolate_clip_length", None)
            st.session_state["isolate_base_name"] = resolved_name
            st.session_state["isolate_source_audio_path"] = str(audio_path)
            st.session_state["isolate_run_dir"] = str(output_dir)
            # Consumed — clear so it doesn't linger for unrelated future separations.
            st.session_state.pop("carry_over_audio_path", None)
            st.session_state.pop("carry_over_audio_name", None)
            st.session_state.pop("isolate_volumes_db", None)
            st.session_state.pop("isolate_master_volume_db", None)
            st.session_state.pop("isolate_mixer_state", None)
            st.session_state.pop("isolate_mix_ready", None)
            st.session_state.pop("isolate_mix_fp", None)
            st.session_state.pop("isolate_zip_fp", None)
            _increment_upload_key()

            new_stem_paths = {
                name: Path(path)
                for name, path in artifacts.items()
                if name
                not in (
                    "guitar_split_diagnostics",
                    "stem_presence_diagnostics",
                    "bass_bleed_diagnostics",
                )
                and Path(path).suffix.lower() == ".wav"
            }
            if new_stem_paths:
                st.session_state["isolate_results_fp"] = _artifact_fingerprint(new_stem_paths)

            presence = _load_stem_presence(artifacts)
            produced_stem_names = [
                name
                for name, path in artifacts.items()
                if name != "guitar_split_diagnostics"
                and name != "stem_presence_diagnostics"
                and name != "bass_bleed_diagnostics"
                and Path(path).suffix.lower() == ".wav"
            ]
            custom_stems = choice["custom_stems"]
            st.session_state["isolate_selected_stems"] = (
                custom_selected_stems(produced_stem_names, custom_stems)
                if custom_stems
                else default_isolate_selected_stems(produced_stem_names, presence)
            )
            stem_count = sum(
                1
                for name, path in artifacts.items()
                if Path(path).suffix.lower() == ".wav"
                and name
                not in (
                    "guitar_split_diagnostics",
                    "stem_presence_diagnostics",
                    "bass_bleed_diagnostics",
                )
            )
            st.session_state["isolate_flash"] = (
                f"Separated {stem_count} tracks. Live mixer and downloads are below."
            )
            write_run_metadata(
                output_dir,
                page="isolate",
                title=st.session_state["isolate_base_name"],
                artifacts=artifacts,
                owner=browser_id,
            )
            st.rerun()

        except Exception as exc:
            st.error(
                "Separation failed — your file and settings are still here, "
                "so you can just try again."
            )
            with _stateful_expander(
                "Technical details", key="isolate_error_details_expanded", default=False
            ):
                st.code(str(exc))
            return

    artifacts_map = st.session_state.get("isolate_artifacts")
    if not artifacts_map:
        return

    if should_hide_stale_results(
        pending_upload_fp=st.session_state.get("isolate_upload_fp"),
        has_artifacts=True,
    ):
        return

    if flash := st.session_state.pop("isolate_flash", None):
        st.success(flash)

    base_name = st.session_state.get("isolate_base_name", "stems")
    stem_paths = _stem_paths_from_artifacts(artifacts_map)
    if not stem_paths:
        return

    st.session_state["isolate_results_fp"] = _artifact_fingerprint(stem_paths)

    presence = _load_stem_presence(artifacts_map)

    bass_bleed = _load_bass_bleed_diagnostics(artifacts_map)
    if bass_bleed.get("flagged"):
        st.warning(
            "Guitar check: "
            f"{bass_bleed.get('reason', 'this track may contain extra bass bleed')}"
        )

    guitar_split = _load_guitar_split_diagnostics(artifacts_map)
    if guitar_split.get("outcome") == "lead_rhythm":
        if guitar_split.get("low_confidence") or guitar_split.get("forced_emit"):
            st.warning(
                "Lead/Rhythm guitar split (best effort, lower confidence): "
                f"{guitar_split.get('reason', '')}"
            )
        else:
            st.info(
                "Lead/Rhythm guitar split: "
                f"{guitar_split.get('reason', 'split applied')}"
            )

    with _stateful_expander(
        "Choose tracks for the mixer and downloads",
        key="isolate_track_picker_expanded",
        default=True,
    ):
        _render_stem_presence_selector(
            stem_paths, presence, _artifact_fingerprint(stem_paths)
        )

    selected_stems = st.session_state.get("isolate_selected_stems", {})
    selected_stem_paths = {
        name: path for name, path in stem_paths.items() if selected_stems.get(name, True)
    }

    run_dir = Path(st.session_state.get("isolate_run_dir", next(iter(stem_paths.values())).parent))

    st.subheader("Live mixer")
    region_caption = st.session_state.get("isolate_region_label")
    source_audio_path = st.session_state.get("isolate_source_audio_path")
    clip_length = st.session_state.get("isolate_clip_length")
    source_note = (
        f" from `{Path(source_audio_path).name}`" if source_audio_path else ""
    )
    if region_caption:
        length_note = f" ({clip_length:.0f} s)" if clip_length else ""
        st.caption(f"**{base_name}** — {region_caption}{length_note}{source_note}")
    else:
        st.caption(f"**{base_name}**{source_note}")
    mixer_state = _render_live_mixer(
        selected_stem_paths, track_title=base_name, base_name=base_name
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

    if not selected_stem_paths:
        st.subheader("Downloads")
        st.info(
            'Select at least one track under "Choose tracks for the mixer and downloads".'
        )
        return

    # Prepare zip + mix before the Downloads heading so Streamlit does not paint a
    # ghost second "Downloads" while blocking on mix export.
    zip_bytes = _cached_zip_bytes(selected_stem_paths, base_name, run_dir)
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
            st.warning(f"Could not build current mix export: {exc}")

    st.subheader("Downloads")
    st.download_button(
        label="Download all tracks (.zip)",
        data=zip_bytes,
        file_name=st.session_state.get("isolate_zip_name", f"{base_name}_stems.zip"),
        mime="application/zip",
        key="dl_zip",
        type="primary",
    )

    if ready:
        st.download_button(
            label="Download current mix",
            data=Path(ready).read_bytes(),
            file_name=f"{base_name}_current_mix.wav",
            mime="audio/wav",
            key="dl_current_mix",
            help="Uses the live mixer's current volume / mute / solo settings.",
        )

    source_audio_path = st.session_state.get("isolate_source_audio_path")
    if source_audio_path and Path(source_audio_path).exists():
        if st.button("Make a tab PDF from this →"):
            st.session_state["carry_over_audio_path"] = source_audio_path
            st.session_state["carry_over_audio_name"] = Path(source_audio_path).name
            st.switch_page(str(Path(__file__).with_name("tab_pdf.py")))


main()
