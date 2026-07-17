"""Streamlit page: multi-stem Audio Isolation with mixer board."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from ui.common import ensure_src_path, run_output_dir, save_upload

ensure_src_path()

from audio_to_tab.isolate import (  # noqa: E402
    DEMUCS_INSTALL_HINT,
    IsolateConfig,
    SUPPORTED_MODELS,
    separate_stems,
)
from audio_to_tab.mixer import (  # noqa: E402
    audible_stems,
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
    "guitar1": "Experimental stereo split",
    "guitar2": "Experimental stereo split",
}


def _init_mixer_state(stem_names: list[str]) -> None:
    muted = st.session_state.setdefault("isolate_muted", {})
    soloed = st.session_state.setdefault("isolate_soloed", {})
    for name in stem_names:
        muted.setdefault(name, False)
        soloed.setdefault(name, False)


def _audible_rule_text(stem_names: list[str], muted: dict[str, bool], soloed: dict[str, bool]) -> str:
    active_solo = [n for n in stem_names if soloed.get(n, False)]
    if active_solo:
        labels = ", ".join(stem_display_name(n) for n in active_solo)
        return f"Solo active — only these stems are heard: {labels} (Mute ignored)."
    audible = audible_stems(stem_names, muted=muted, soloed=soloed)
    if not audible:
        return "All stems muted — nothing will play."
    labels = ", ".join(stem_display_name(n) for n in audible)
    return f"Audible mix: {labels}"


def _render_waveform(path: Path, key: str) -> None:
    peaks = waveform_peaks(path)
    chart_df = pd.DataFrame({"amp": peaks})
    st.line_chart(chart_df, height=120, use_container_width=True)


def _render_stem_board(
    stem_paths: dict[str, Path],
    base_name: str,
    *,
    cols_per_row: int = 3,
) -> None:
    stem_names = sort_stem_names(stem_paths.keys())
    _init_mixer_state(stem_names)
    muted = st.session_state["isolate_muted"]
    soloed = st.session_state["isolate_soloed"]

    st.caption(_audible_rule_text(stem_names, muted, soloed))

    for row_start in range(0, len(stem_names), cols_per_row):
        row_names = stem_names[row_start : row_start + cols_per_row]
        cols = st.columns(len(row_names))
        for col, name in zip(cols, row_names):
            path = stem_paths[name]
            with col:
                label = stem_display_name(name)
                badges = []
                if soloed.get(name):
                    badges.append("SOLO")
                elif muted.get(name):
                    badges.append("MUTED")
                badge_txt = f" · **{' · '.join(badges)}**" if badges else ""
                st.markdown(f"**{label}**{badge_txt}")
                if hint := STEM_HINTS.get(name):
                    st.caption(hint)
                _render_waveform(path, key=f"wf_{name}")
                c1, c2 = st.columns(2)
                with c1:
                    muted[name] = st.checkbox("Mute", value=muted.get(name, False), key=f"mute_{name}")
                with c2:
                    soloed[name] = st.checkbox("Solo", value=soloed.get(name, False), key=f"solo_{name}")
                st.download_button(
                    label=f"Download {label}",
                    data=path.read_bytes(),
                    file_name=f"{base_name}_{name}.wav",
                    mime="audio/wav",
                    key=f"dl_{name}",
                )

    st.session_state["isolate_muted"] = muted
    st.session_state["isolate_soloed"] = soloed

    audible = audible_stems(stem_names, muted=muted, soloed=soloed)
    if st.button("Play heard mix", type="primary", disabled=not audible):
        mix_key = hashlib.sha256(",".join(sorted(audible)).encode()).hexdigest()[:16]
        out_dir = path.parent if (path := next(iter(stem_paths.values()), None)) else Path(".")
        mix_path = out_dir / f"_heard_mix_{mix_key}.wav"
        try:
            mix_stems_to_wav(stem_paths, audible, mix_path)
            st.audio(mix_path.read_bytes(), format="audio/wav")
        except Exception as exc:
            st.error(f"Could not build mix: {exc}")


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
        dual_guitar = st.checkbox(
            "Enable dual-guitar split (experimental)",
            value=False,
            help=(
                "After separation, try to split the guitar stem into Guitar 1 and Guitar 2 "
                "using a stereo heuristic. Only works when the guitar stem has distinct L/R content."
            ),
        )
    else:
        dual_guitar = False
        st.caption("Dual-guitar split requires the 6-stem model (htdemucs_6s) with a guitar stem.")

    quality = st.selectbox(
        "Quality",
        options=["fast", "balanced", "high", "extreme"],
        index=1,
        help="Higher quality uses more Demucs shifts/overlap and is much slower on CPU.",
    )
    max_duration = st.slider("Max duration (seconds)", min_value=15, max_value=300, value=90, step=15)
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
            max_duration_sec=float(max_duration),
            dual_guitar=dual_guitar,
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

            st.success(f"Separated {len(artifacts)} stem(s).")
            st.session_state["isolate_artifacts"] = {k: str(v) for k, v in artifacts.items()}
            st.session_state["isolate_base_name"] = Path(uploaded.name).stem
            st.session_state["isolate_dual_guitar_requested"] = dual_guitar
            st.session_state.pop("isolate_muted", None)
            st.session_state.pop("isolate_soloed", None)

            if dual_guitar and "guitar" in artifacts and "guitar1" not in artifacts:
                st.info(
                    "Dual-guitar split was not applied — the separated guitar stem did not pass "
                    "the stereo heuristic (likely one guitar or mono content)."
                )

        except Exception as exc:
            st.error(f"Isolation failed: {exc}")
            return

    artifacts_map = st.session_state.get("isolate_artifacts")
    if not artifacts_map:
        return

    base_name = st.session_state.get("isolate_base_name", "stems")
    stem_paths = {name: Path(path) for name, path in artifacts_map.items() if Path(path).exists()}
    if not stem_paths:
        return

    st.subheader("Stem board")
    _render_stem_board(stem_paths, base_name)

    st.subheader("Downloads")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, path in sorted(stem_paths.items()):
            zf.writestr(f"{name}.wav", path.read_bytes())
    st.download_button(
        label="Download all stems (.zip)",
        data=buf.getvalue(),
        file_name=f"{base_name}_stems.zip",
        mime="application/zip",
        key="dl_zip",
    )


main()
