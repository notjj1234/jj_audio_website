"""Streamlit page: multi-stem Audio Isolation with live stem mixer."""

from __future__ import annotations

import hashlib
import io
import json
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st
from streamlit_local_storage import LocalStorage

from ui.common import (
    delete_run,
    ensure_src_path,
    list_recent_runs,
    run_output_dir,
    save_upload,
    write_run_metadata,
)
from ui.isolate_state import (
    ISOLATION_STAGE_ORDER,
    format_elapsed,
    format_progress_label,
    should_hide_stale_results,
    stage_progress_percent,
    sync_output_name_on_upload,
)
from ui.media import cleanup_mix_artifacts, ensure_mixer_audio_paths, stem_media_urls
from ui.stem_mixer_component import component_build_available, stem_mixer

ensure_src_path()

from audio_to_tab.isolate import (  # noqa: E402
    DEMUCS_INSTALL_HINT,
    IsolateConfig,
    SUPPORTED_MODELS,
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

_MODEL_HELP = {
    "htdemucs_6s": "6 stems: drums, bass, other, vocals, guitar, piano (piano often has artifacts)",
    "htdemucs": "4 stems: drums, bass, other, vocals — solid general quality",
    "htdemucs_ft": "4 stems, fine-tuned — slower, slightly better quality",
}

_MODEL_SHORT = {
    "htdemucs_6s": "htdemucs_6s (6 stems)",
    "htdemucs": "htdemucs (4 stems)",
    "htdemucs_ft": "htdemucs_ft (4 stems, fine-tuned)",
}

STEM_HINTS = {
    "piano": "May contain artifacts (Demucs limitation)",
    "lead_guitar": "Always produced from the guitar stem (best-effort when confidence is low)",
    "rhythm_guitar": "Always produced from the guitar stem (best-effort when confidence is low)",
    "guitar1": "Legacy spatial label",
    "guitar2": "Legacy spatial label",
}

_LS_USER_ID_KEY = "isolate_user_id"
_LS_COMPONENT_KEY = "isolate_local_storage"


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
) -> str:
    parts = []
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
                    help_text = "No detection data available for this stem."
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
) -> Path:
    mix_path = run_dir / "current_mix.wav"
    gains = effective_linear_gains(
        stem_names,
        muted={n: bool(muted.get(n, False)) for n in stem_names},
        soloed={n: bool(soloed.get(n, False)) for n in stem_names},
        volume_db={n: float(volumes_db.get(n, DB_DEFAULT)) for n in stem_names},
    )
    mix_stems_to_wav(selected_stem_paths, output_path=mix_path, gains=gains)
    fp = _mixer_export_fingerprint(stem_names, volumes_db, muted, soloed)
    st.session_state["isolate_mix_ready"] = str(mix_path)
    st.session_state["isolate_mix_fp"] = fp
    return mix_path


def _render_live_mixer(
    stem_paths: dict[str, Path], *, track_title: str = "", base_name: str = "stems"
) -> dict | None:
    if not component_build_available():
        st.error(
            "Live stem mixer frontend is not built. "
            "Run: npm install && npm run build in ui/stem_mixer_component/frontend "
            "(or .\\scripts\\dev.ps1 mixer-build)."
        )
        return None

    mixer_paths = ensure_mixer_audio_paths(stem_paths)
    if mixer_paths != stem_paths:
        st.caption(
            "Using downsampled preview audio for browser playback (original WAVs used for downloads)."
        )

    try:
        urls = stem_media_urls(mixer_paths)
        # Registered separately (full-quality originals) so per-stem downloads inside
        # the mixer dropdowns are never the downsampled browser-preview audio.
        download_urls = stem_media_urls(stem_paths, coord_prefix="isolate.download")
    except Exception as exc:
        st.error(f"Could not register stem media URLs: {exc}")
        return None

    stem_names = sort_stem_names(stem_paths.keys())
    volumes = st.session_state.setdefault("isolate_volumes_db", {})
    for name in stem_names:
        volumes.setdefault(name, DB_DEFAULT)

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
        track_title=track_title,
        key=f"stem_mixer_{fingerprint}",
    )


def _render_separation_controls() -> tuple[str, str, str, float | None, object, str]:
    """Model + upload; Quality/duration are common first-run decisions and stay at the top
    level. Device is the one setting almost nobody without a configured GPU touches, so it
    stays under Advanced."""
    model = st.selectbox(
        "Separation model",
        options=list(SUPPORTED_MODELS),
        index=0,
        format_func=lambda m: _MODEL_SHORT.get(m, m),
        help=" | ".join(f"{k}: {v}" for k, v in _MODEL_HELP.items()),
    )
    if model == "htdemucs_6s":
        st.info(
            "Note: On the 6-stem model, guitar quality is okay; "
            "piano often has bleeding/artifacts (Demucs limitation)."
        )

    quality = st.selectbox(
        "Quality",
        options=["fast", "balanced", "high", "extreme"],
        index=1,
        help="Higher quality uses more Demucs shifts/overlap and is much slower on CPU.",
    )
    limit_duration = st.checkbox(
        "Limit duration",
        value=False,
        help="Off = process the full song. On = trim to a max length for faster previews.",
    )
    max_duration_sec: float | None = None
    if limit_duration:
        max_duration_sec = float(
            st.slider(
                "Max duration (seconds)",
                min_value=15,
                max_value=300,
                value=90,
                step=15,
            )
        )
    else:
        st.caption(
            "Full song will be processed. Demucs on CPU can take a long time for long tracks."
        )

    with st.expander("Advanced", expanded=False):
        device = st.selectbox("Device", options=["cpu", "cuda"], index=0)

    uploaded = st.file_uploader(
        "Upload MP3 / WAV / FLAC / M4A",
        type=["mp3", "wav", "flac", "m4a"],
        key=f"isolate_upload_{st.session_state.get('isolate_upload_key', 0)}",
    )
    _sync_upload_output_name(uploaded)
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
    output_name = st.text_input(
        "Output name",
        value=default_name,
        help="Used for downloaded file names. Defaults to the uploaded file's name.",
        key="isolate_output_name",
    )
    return model, quality, device, max_duration_sec, uploaded, output_name


def main() -> None:
    st.title("Audio Isolation")
    st.caption(
        "Separate a mix into individual instrument stems with Demucs (free/open-source). "
        "CPU separation is slow — expect roughly the track length or longer."
    )

    with st.expander("How this works"):
        st.markdown(
            "1. **Demucs** (an open-source separation model) splits your uploaded mix into "
            "individual instrument tracks — called **stems** (e.g. drums, bass, vocals, "
            "guitar) — by learning what each instrument typically sounds like.\n"
            "2. Once separated, use the **Live mixer** to listen to any combination of stems "
            "at custom volumes (mute/solo included) without re-running Demucs.\n"
            "3. Download individual stems, everything as a zip, or a custom mixdown of the "
            "levels you dialed in.\n\n"
            "Separation quality varies by instrument and model choice — see the model "
            "picker's tooltip below for tradeoffs."
        )

    demucs_ok = is_demucs_available()
    if not demucs_ok:
        st.error(
            "Demucs is required for Audio Isolation and is not installed. "
            f"{DEMUCS_INSTALL_HINT}"
        )
        return

    has_results = bool(st.session_state.get("isolate_artifacts"))
    browser_id = _get_browser_user_id()

    with st.expander("Separation settings", expanded=not has_results):
        model, quality, device, max_duration_sec, uploaded, output_name = (
            _render_separation_controls()
        )

    pending_new_upload = uploaded is not None
    pending_upload_fp = st.session_state.get("isolate_upload_fp")
    if should_hide_stale_results(
        pending_upload_fp=pending_upload_fp,
        has_artifacts=has_results,
    ):
        upload_name = uploaded.name if uploaded else "New file"
        st.info(
            f"**{upload_name}** is ready — click **Separate stems** to replace the "
            "current results."
        )

    recent_runs = list_recent_runs("isolate", owner=browser_id)
    if recent_runs:
        with st.expander(
            f"Recent isolations ({len(recent_runs)})",
            expanded=st.session_state.get("isolate_recent_expanded", False),
        ):
            st.caption(
                "Reopen a past isolation's mixer and downloads without re-uploading or "
                "re-running Demucs."
            )
            if pending_new_upload:
                st.caption(
                    "Finish or clear your new upload before reopening a past isolation."
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
                    st.write(run.get("title") or "stems")
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
                        title = run.get("title") or "stems"
                        st.session_state["isolate_base_name"] = title
                        st.session_state["isolate_run_dir"] = run["run_dir"]
                        st.session_state["isolate_output_name"] = title
                        st.session_state.pop("isolate_volumes_db", None)
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
                        # Keep "Recent isolations" open across the rerun below — without
                        # this the expander resets to collapsed and you lose your place.
                        st.session_state["isolate_recent_expanded"] = True
                        deleted = delete_run(run["run_dir"])
                        if deleted:
                            if st.session_state.get("isolate_run_dir") == run["run_dir"]:
                                for key in (
                                    "isolate_artifacts",
                                    "isolate_base_name",
                                    "isolate_run_dir",
                                    "isolate_volumes_db",
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
                            st.error("Could not delete that isolation.")

    # Kept outside the collapsible settings so it stays reachable (e.g. to run again on a
    # new file) without needing to re-open "Separation settings" after a result appears.
    run_separate = st.button(
        "Separate stems",
        type="primary",
        disabled=not demucs_ok,
        key="isolate_separate",
    )
    st.caption(
        "Separation can take roughly the track length or longer on CPU. There's currently "
        "no way to cancel once started, and closing this tab may not stop server-side "
        "processing."
    )

    if run_separate:
        carry_over_path = st.session_state.get("carry_over_audio_path")
        using_carry_over = bool(
            not uploaded and carry_over_path and Path(carry_over_path).exists()
        )
        if not uploaded and not using_carry_over:
            st.error("Upload an audio file.")
            return

        output_dir = run_output_dir()
        config = IsolateConfig(
            model=model,
            quality=quality,
            device=device,
            max_duration_sec=max_duration_sec,
        )

        # Weighted stage progress — Demucs dominates runtime.
        separation_started = time.monotonic()

        try:
            with st.status("Starting isolation…", expanded=True) as status:
                progress_bar = st.progress(0.0)
                progress_label = st.empty()

                def on_progress(stage: str, message: str) -> None:
                    elapsed = format_elapsed(time.monotonic() - separation_started)
                    if stage in ISOLATION_STAGE_ORDER:
                        pct = stage_progress_percent(stage)
                        progress_bar.progress(pct)
                        label = format_progress_label(pct, message)
                        if stage == "separate":
                            label = f"{label} (elapsed {elapsed})"
                        progress_label.caption(label)
                    status.update(label=f"[{stage}] {message} · {elapsed}")

                if uploaded:
                    audio_path = save_upload(uploaded)
                else:
                    audio_path = Path(carry_over_path)
                artifacts = separate_stems(
                    audio_path=audio_path,
                    output_dir=output_dir,
                    config=config,
                    on_progress=on_progress,
                )

            cleanup_mix_artifacts(output_dir)
            st.session_state["isolate_artifacts"] = {k: str(v) for k, v in artifacts.items()}
            resolved_name = output_name.strip() or Path(uploaded.name).stem if uploaded else audio_path.stem
            st.session_state["isolate_base_name"] = resolved_name
            st.session_state["isolate_source_audio_path"] = str(audio_path)
            st.session_state["isolate_run_dir"] = str(output_dir)
            # Consumed — clear so it doesn't linger for unrelated future separations.
            st.session_state.pop("carry_over_audio_path", None)
            st.session_state.pop("carry_over_audio_name", None)
            st.session_state.pop("isolate_volumes_db", None)
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
            st.session_state["isolate_selected_stems"] = default_isolate_selected_stems(
                produced_stem_names, presence
            )
            # Rerun so Separation settings collapses and results sit near the top.
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
                f"Separated {stem_count} stem(s). Live mixer and downloads are below."
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
                "Isolation failed — your file and settings are still here, "
                "so you can just try again."
            )
            with st.expander("Technical details"):
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
            "Guitar stem check: "
            f"{bass_bleed.get('reason', 'anomalously bass-heavy content detected')}"
        )

    guitar_split = _load_guitar_split_diagnostics(artifacts_map)
    if guitar_split.get("outcome") == "lead_rhythm":
        if guitar_split.get("low_confidence") or guitar_split.get("forced_emit"):
            st.warning(
                "Lead/Rhythm guitar split (best-effort, low confidence): "
                f"{guitar_split.get('reason', '')}"
            )
        else:
            st.info(
                "Lead/Rhythm guitar split: "
                f"{guitar_split.get('reason', 'split applied')}"
            )

    with st.expander("Include stems (mixer & downloads)", expanded=False):
        st.caption(
            "Choose which already-separated stems feed the mixer and downloads below "
            "(does not re-run Demucs — the Separation model above already produced these). "
            "Lead/Rhythm Guitar are included by default when present."
        )
        _render_stem_presence_selector(
            stem_paths, presence, _artifact_fingerprint(stem_paths)
        )

    selected_stems = st.session_state.get("isolate_selected_stems", {})
    selected_stem_paths = {
        name: path for name, path in stem_paths.items() if selected_stems.get(name, True)
    }

    run_dir = Path(st.session_state.get("isolate_run_dir", next(iter(stem_paths.values())).parent))

    st.subheader("Live mixer")
    st.caption(f"**Track:** {base_name}")
    source_audio_path = st.session_state.get("isolate_source_audio_path")
    if source_audio_path and Path(source_audio_path).exists():
        st.caption(f"Source file: `{Path(source_audio_path).name}`")
    st.caption(
        "Play all stems in sync. Levels apply in the mixer without re-running Demucs or "
        "resetting the playhead. Mixer state is sent to the page when you finish adjusting "
        "(for mix export). Volume: −60 dB to +24 dB (0 dB = unity). Open **Waveform & "
        "download** on any instrument for its waveform and a full-quality WAV download."
    )
    mixer_state = _render_live_mixer(
        selected_stem_paths, track_title=base_name, base_name=base_name
    )
    if mixer_state:
        st.session_state["isolate_mixer_state"] = mixer_state
        if "volumesDb" in mixer_state:
            st.session_state["isolate_volumes_db"] = {
                k: float(v) for k, v in mixer_state["volumesDb"].items()
            }

    st.subheader("Downloads")
    if not selected_stem_paths:
        st.info("Select at least one stem under \"Include stems\" to enable downloads.")
        return

    zip_bytes = _cached_zip_bytes(selected_stem_paths, base_name, run_dir)
    st.download_button(
        label="Download all stems (.zip)",
        data=zip_bytes,
        file_name=st.session_state.get("isolate_zip_name", f"{base_name}_stems.zip"),
        mime="application/zip",
        key="dl_zip",
        type="primary",
    )

    stem_names = sort_stem_names(selected_stem_paths.keys())
    state = st.session_state.get("isolate_mixer_state") or {}
    volumes_db = state.get("volumesDb") or st.session_state.get("isolate_volumes_db") or {}
    muted = state.get("muted") or {n: False for n in stem_names}
    soloed = state.get("soloed") or {n: False for n in stem_names}
    export_fp = _mixer_export_fingerprint(stem_names, volumes_db, muted, soloed)
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
            )
            ready = st.session_state.get("isolate_mix_ready")
        except Exception as exc:
            st.session_state.pop("isolate_mix_ready", None)
            st.session_state.pop("isolate_mix_fp", None)
            ready = None
            st.warning(f"Could not build current mix export: {exc}")

    if ready:
        st.download_button(
            label="Download current mix",
            data=Path(ready).read_bytes(),
            file_name=f"{base_name}_current_mix.wav",
            mime="audio/wav",
            key="dl_current_mix",
            help="Reflects the live mixer's current volume / mute / solo settings.",
        )

    source_audio_path = st.session_state.get("isolate_source_audio_path")
    if source_audio_path and Path(source_audio_path).exists():
        if st.button("Also make a tab PDF from this →"):
            st.session_state["carry_over_audio_path"] = source_audio_path
            st.session_state["carry_over_audio_name"] = Path(source_audio_path).name
            st.switch_page(str(Path(__file__).with_name("tab_pdf.py")))


main()
