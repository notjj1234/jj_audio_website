"""Streamlit web UI for audio-to-guitar-tab PDF conversion."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st

# Ensure package imports work when launched via streamlit from repo root
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from audio_to_tab.pipeline import (  # noqa: E402
    YOUTUBE_DISCLAIMER,
    DEMUCS_INSTALL_HINT,
    PipelineConfig,
    run_pipeline,
)
from audio_to_tab.separate import is_demucs_available  # noqa: E402

DATA_DIR = _REPO_ROOT / "data" / "ui_runs"


def _save_upload(uploaded_file) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = DATA_DIR / str(uuid.uuid4())
    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / uploaded_file.name
    dest.write_bytes(uploaded_file.getvalue())
    return dest


def _run_output_dir() -> Path:
    out = DATA_DIR / str(uuid.uuid4())
    out.mkdir(parents=True, exist_ok=True)
    return out


def main() -> None:
    st.set_page_config(page_title="Audio to Tab PDF", page_icon="🎸", layout="centered")
    st.title("Audio → Guitar Tab PDF")
    st.caption(
        "Draft transcription tool (free/open-source). "
        "Full songs need guitar stem separation (Demucs). Solo guitar can skip it."
    )

    demucs_ok = is_demucs_available()
    if not demucs_ok:
        st.info(
            "Stem separation is unavailable (Demucs not installed). "
            "Conversions will run on the full mix — quality may be lower for songs with drums/bass. "
            f"{DEMUCS_INSTALL_HINT}"
        )

    title = st.text_input("Tab title", value="Guitar Tab")
    separate_stems = st.toggle(
        "Separate guitar stem (Demucs) — required for full mixes",
        value=demucs_ok,
        disabled=not demucs_ok,
        help=(
            "Turn off for solo guitar uploads (much faster). "
            "Install Demucs to enable: make install-demucs"
            if not demucs_ok
            else "Turn off only for solo guitar uploads (much faster)."
        ),
    )
    max_duration = st.slider("Max duration (seconds)", min_value=15, max_value=300, value=90, step=15)

    with st.expander("Advanced transcription settings"):
        mix_aware = st.checkbox("Mix-aware filtering (stricter note filters)", value=True)
        tempo_override = st.number_input(
            "Tempo override (BPM, 0 = auto)",
            min_value=0.0,
            max_value=240.0,
            value=0.0,
            step=1.0,
        )
        onset_threshold = st.slider("Onset threshold", 0.3, 0.9, 0.5, 0.05)
        frame_threshold = st.slider("Frame threshold", 0.2, 0.8, 0.3, 0.05)

    uploaded = st.file_uploader(
        "Upload MP3 / WAV / FLAC / M4A",
        type=["mp3", "wav", "flac", "m4a"],
    )
    youtube_url = st.text_input("Or paste a YouTube URL")
    st.caption(YOUTUBE_DISCLAIMER)

    if st.button("Convert to tab PDF", type="primary"):
        if not uploaded and not youtube_url.strip():
            st.error("Upload an audio file or enter a YouTube URL.")
            return

        effective_separate = separate_stems and demucs_ok
        skipped_separation = separate_stems and not demucs_ok

        output_dir = _run_output_dir()
        config = PipelineConfig(
            separate_stems=effective_separate,
            max_duration_sec=float(max_duration),
            title=title or "Guitar Tab",
            mix_aware_filtering=mix_aware,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            tempo_bpm_override=tempo_override if tempo_override > 0 else None,
        )

        try:
            with st.status("Starting…", expanded=True) as status:

                def on_progress(stage: str, message: str) -> None:
                    status.update(label=f"[{stage}] {message}")

                audio_path = _save_upload(uploaded) if uploaded else None
                url = youtube_url.strip() or None

                artifacts = run_pipeline(
                    audio_path=audio_path,
                    youtube_url=url,
                    output_dir=output_dir,
                    config=config,
                    on_progress=on_progress,
                )

            st.success("Conversion complete.")
            if skipped_separation:
                st.info(
                    "Ran without stem separation — install Demucs for better full-mix results. "
                    f"{DEMUCS_INSTALL_HINT}"
                )

            pdf_path = artifacts["pdf"]
            tab_path = artifacts["tab"]
            midi_path = artifacts["midi"]

            st.download_button(
                label="Download PDF",
                data=pdf_path.read_bytes(),
                file_name=f"{title or 'guitar_tab'}.pdf",
                mime="application/pdf",
            )
            with st.expander("Other downloads"):
                st.download_button(
                    label="Download ASCII tab (.tab)",
                    data=tab_path.read_text(encoding="utf-8"),
                    file_name=f"{title or 'guitar_tab'}.tab",
                    mime="text/plain",
                )
                st.download_button(
                    label="Download MIDI (.mid)",
                    data=midi_path.read_bytes(),
                    file_name=f"{title or 'guitar_tab'}.mid",
                    mime="audio/midi",
                )
                stem_path = artifacts.get("guitar_stem")
                if stem_path and stem_path.exists():
                    st.download_button(
                        label="Download guitar stem (.wav)",
                        data=stem_path.read_bytes(),
                        file_name=f"{title or 'guitar_tab'}_guitar_stem.wav",
                        mime="audio/wav",
                    )

        except Exception as exc:
            st.error(f"Conversion failed: {exc}")


if __name__ == "__main__":
    main()
