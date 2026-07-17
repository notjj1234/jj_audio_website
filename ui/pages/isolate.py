"""Streamlit page: multi-stem Audio Isolation with live stem mixer."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from ui.common import ensure_src_path, run_output_dir, save_upload
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

STEM_HINTS = {
    "piano": "May contain artifacts (Demucs limitation)",
    "lead_guitar": "Always produced from the guitar stem (best-effort when confidence is low)",
    "rhythm_guitar": "Always produced from the guitar stem (best-effort when confidence is low)",
    "guitar1": "Legacy spatial label",
    "guitar2": "Legacy spatial label",
}


def _render_waveform(path: Path) -> None:
    peaks = waveform_peaks(path)
    chart_df = pd.DataFrame({"amp": peaks})
    st.line_chart(chart_df, height=120, use_container_width=True)


def _artifact_fingerprint(stem_paths: dict[str, Path]) -> str:
    payload = "|".join(f"{k}:{v}" for k, v in sorted((n, str(p)) for n, p in stem_paths.items()))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


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


def _render_stem_downloads(stem_paths: dict[str, Path], base_name: str) -> None:
    stem_names = sort_stem_names(stem_paths.keys())
    cols_per_row = 3
    for row_start in range(0, len(stem_names), cols_per_row):
        row_names = stem_names[row_start : row_start + cols_per_row]
        cols = st.columns(len(row_names))
        for col, name in zip(cols, row_names):
            path = stem_paths[name]
            with col:
                label = stem_display_name(name)
                st.markdown(f"**{label}**")
                if hint := STEM_HINTS.get(name):
                    st.caption(hint)
                _render_waveform(path)
                st.download_button(
                    label=f"Download {label}",
                    data=path.read_bytes(),
                    file_name=f"{base_name}_{name}.wav",
                    mime="audio/wav",
                    key=f"dl_{name}",
                )


def _render_live_mixer(stem_paths: dict[str, Path]) -> dict | None:
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
    except Exception as exc:
        st.error(f"Could not register stem media URLs: {exc}")
        return None

    stem_names = sort_stem_names(stem_paths.keys())
    volumes = st.session_state.setdefault("isolate_volumes_db", {})
    for name in stem_names:
        volumes.setdefault(name, DB_DEFAULT)

    stems_arg = [
        {"id": name, "label": stem_display_name(name), "url": urls[name]}
        for name in stem_names
        if name in urls
    ]
    fingerprint = _artifact_fingerprint(stem_paths)
    return stem_mixer(
        stems_arg,
        initial_volumes_db={n: float(volumes.get(n, DB_DEFAULT)) for n in stem_names},
        initial_muted={n: False for n in stem_names},
        initial_soloed={n: False for n in stem_names},
        key=f"stem_mixer_{fingerprint}",
    )


def main() -> None:
    st.title("Audio Isolation")
    st.caption(
        "Separate a mix into individual instrument stems with Demucs (free/open-source). "
        "CPU separation is slow — expect roughly the track length or longer."
    )

    demucs_ok = is_demucs_available()
    if not demucs_ok:
        st.error(
            "Demucs is required for Audio Isolation and is not installed. "
            f"{DEMUCS_INSTALL_HINT}"
        )
        return

    model = st.selectbox(
        "Separation model",
        options=list(SUPPORTED_MODELS),
        index=0,
        format_func=lambda m: f"{m} — {_MODEL_HELP.get(m, '')}",
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
            st.slider("Max duration (seconds)", min_value=15, max_value=300, value=90, step=15)
        )
    else:
        st.caption("Full song will be processed. Demucs on CPU can take a long time for long tracks.")
    device = st.selectbox("Device", options=["cpu", "cuda"], index=0)

    uploaded = st.file_uploader(
        "Upload MP3 / WAV / FLAC / M4A",
        type=["mp3", "wav", "flac", "m4a"],
        key="isolate_upload",
    )

    if st.button("Separate stems", type="primary", disabled=not demucs_ok):
        if not uploaded:
            st.error("Upload an audio file.")
            return

        output_dir = run_output_dir()
        config = IsolateConfig(
            model=model,
            quality=quality,
            device=device,
            max_duration_sec=max_duration_sec,
        )

        try:
            with st.status("Starting isolation…", expanded=True) as status:

                def on_progress(stage: str, message: str) -> None:
                    status.update(label=f"[{stage}] {message}")

                audio_path = save_upload(uploaded)
                artifacts = separate_stems(
                    audio_path=audio_path,
                    output_dir=output_dir,
                    config=config,
                    on_progress=on_progress,
                )

            cleanup_mix_artifacts(output_dir)
            st.success(f"Separated {len(artifacts)} stem(s).")
            st.session_state["isolate_artifacts"] = {k: str(v) for k, v in artifacts.items()}
            st.session_state["isolate_base_name"] = Path(uploaded.name).stem
            st.session_state["isolate_run_dir"] = str(output_dir)
            st.session_state.pop("isolate_volumes_db", None)
            st.session_state.pop("isolate_mixer_state", None)
            st.session_state.pop("isolate_mix_ready", None)

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

        except Exception as exc:
            st.error(f"Isolation failed: {exc}")
            return

    artifacts_map = st.session_state.get("isolate_artifacts")
    if not artifacts_map:
        return

    base_name = st.session_state.get("isolate_base_name", "stems")
    stem_paths = {
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
    if not stem_paths:
        return

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

    st.subheader("Detected instruments")
    st.caption(
        "Demucs always separates every stem for the chosen model — these checkboxes only "
        "choose which already-separated stems are used below (mixer, stem board, zip, mix export). "
        "When a guitar stem exists, Lead Guitar and Rhythm Guitar are always produced and "
        "checked by default (best-effort if confidence is low)."
    )
    _render_stem_presence_selector(stem_paths, presence, _artifact_fingerprint(stem_paths))

    selected_stems = st.session_state.get("isolate_selected_stems", {})
    selected_stem_paths = {
        name: path for name, path in stem_paths.items() if selected_stems.get(name, True)
    }

    run_dir = Path(st.session_state.get("isolate_run_dir", next(iter(stem_paths.values())).parent))

    st.subheader("Live mixer")
    st.caption(
        "Play all stems in sync. Volume, mute, and solo update instantly without re-running Demucs "
        "or resetting the playhead. Volume range: −60 dB (silence) to +24 dB (0 dB = unity)."
    )
    mixer_state = _render_live_mixer(selected_stem_paths)
    if mixer_state:
        st.session_state["isolate_mixer_state"] = mixer_state
        if "volumesDb" in mixer_state:
            st.session_state["isolate_volumes_db"] = {
                k: float(v) for k, v in mixer_state["volumesDb"].items()
            }

    st.subheader("Stem board")
    _render_stem_downloads(selected_stem_paths, base_name)

    st.subheader("Downloads")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, path in sorted(selected_stem_paths.items()):
            zf.writestr(f"{name}.wav", path.read_bytes())
    st.download_button(
        label="Download all stems (.zip)",
        data=buf.getvalue(),
        file_name=f"{base_name}_stems.zip",
        mime="application/zip",
        key="dl_zip",
    )

    stem_names = sort_stem_names(selected_stem_paths.keys())
    state = st.session_state.get("isolate_mixer_state") or {}
    volumes_db = state.get("volumesDb") or st.session_state.get("isolate_volumes_db") or {}
    muted = state.get("muted") or {n: False for n in stem_names}
    soloed = state.get("soloed") or {n: False for n in stem_names}
    mix_path = run_dir / "current_mix.wav"

    if st.button(
        "Prepare current mix download",
        help="Builds a WAV from the current live mixer volume / mute / solo settings.",
    ):
        gains = effective_linear_gains(
            stem_names,
            muted={n: bool(muted.get(n, False)) for n in stem_names},
            soloed={n: bool(soloed.get(n, False)) for n in stem_names},
            volume_db={n: float(volumes_db.get(n, DB_DEFAULT)) for n in stem_names},
        )
        try:
            mix_stems_to_wav(selected_stem_paths, output_path=mix_path, gains=gains)
            st.session_state["isolate_mix_ready"] = str(mix_path)
            st.success("Current mix ready.")
        except Exception as exc:
            st.session_state.pop("isolate_mix_ready", None)
            st.warning(f"Could not build current mix export: {exc}")

    ready = st.session_state.get("isolate_mix_ready")
    if ready and Path(ready).exists():
        st.download_button(
            label="Download current mix",
            data=Path(ready).read_bytes(),
            file_name=f"{base_name}_current_mix.wav",
            mime="audio/wav",
            key="dl_current_mix",
        )


main()
