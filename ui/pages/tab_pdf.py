"""Streamlit page: Tab PDF — guitar tab generator."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

import streamlit as st

from ui.common import (
    AUDIO_UPLOAD_TYPES,
    ensure_src_path,
    list_recent_runs,
    run_output_dir,
    save_upload,
    write_run_metadata,
)

ensure_src_path()

from audio_to_tab.pipeline import (  # noqa: E402
    YOUTUBE_DISCLAIMER,
    DEMUCS_INSTALL_HINT,
    PipelineConfig,
    run_pipeline,
)
from audio_to_tab.ingest import is_youtube_url  # noqa: E402
from audio_to_tab.separate import is_demucs_available  # noqa: E402


def main() -> None:
    st.title("Tab PDF (demo)")
    st.caption(
        "Demo only — tabs are rough drafts. Expect wrong notes; not finished sheet music."
    )
    st.warning(
        "Best on short solo-guitar clips. For full songs, isolate guitar first on "
        "**Audio Isolation**."
    )

    demucs_ok = is_demucs_available()
    if not demucs_ok:
        st.info(
            "Stem separation is unavailable (Demucs not installed). "
            "Conversions will run on the full mix — quality may be lower for songs with drums/bass. "
            f"{DEMUCS_INSTALL_HINT}"
        )

    has_results = bool(st.session_state.get("tab_pdf_artifacts"))

    recent_runs = list_recent_runs("tab_pdf")
    if recent_runs:
        with st.expander(f"Recent conversions ({len(recent_runs)})", expanded=False):
            for run in recent_runs:
                run_artifacts = run.get("artifacts", {})
                available = Path(run_artifacts.get("pdf", "")).exists() if run_artifacts else False
                cols = st.columns([3, 1])
                with cols[0]:
                    created_at = run.get("created_at")
                    when = (
                        datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M")
                        if created_at
                        else ""
                    )
                    st.write(run.get("title") or "Guitar Tab")
                    st.caption(when if available else f"{when} — files no longer available")
                with cols[1]:
                    if available and st.button("Reopen", key=f"reopen_tab_{run['run_dir']}"):
                        st.session_state["tab_pdf_artifacts"] = run_artifacts
                        st.session_state["tab_pdf_title"] = run.get("title") or "Guitar Tab"
                        st.session_state["tab_pdf_skipped_separation"] = False
                        st.session_state.pop("tab_pdf_flash", None)
                        st.rerun()

    with st.expander("Conversion settings", expanded=not has_results):
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
            limit_duration = st.checkbox(
                "Limit duration",
                value=False,
                help="Off = process the full track. On = trim to a max length for a faster draft.",
            )
            max_duration: float | None = None
            if limit_duration:
                max_duration = float(
                    st.slider(
                        "Max duration (seconds)", min_value=15, max_value=300, value=90, step=15
                    )
                )
            else:
                st.caption(
                    "Full track will be processed. This can take a long time on CPU for long songs."
                )

        uploaded = st.file_uploader(
            "Upload MP3 / WAV / FLAC / M4A",
            type=AUDIO_UPLOAD_TYPES,
        )
        carry_over_path = st.session_state.get("carry_over_audio_path")
        carry_over_name = st.session_state.get("carry_over_audio_name")
        using_carry_over = bool(
            not uploaded and carry_over_path and Path(carry_over_path).exists()
        )
        if using_carry_over:
            st.caption(
                f"Using audio carried over from Audio Isolation: **{carry_over_name}**. "
                "Upload a file above to use something else instead."
            )
        youtube_enabled = st.checkbox(
            "Download from YouTube",
            value=not bool(getattr(sys, "frozen", False)),
            help=(
                "Off by default in the desktop installer. Enable only if you have rights "
                "to the audio. Arbitrary URLs are rejected."
            ),
        )
        youtube_url = ""
        if youtube_enabled:
            youtube_url = st.text_input("Or paste a YouTube URL")
            st.caption(YOUTUBE_DISCLAIMER)
        elif getattr(sys, "frozen", False):
            st.caption(
                "YouTube download is off in this installer build. Enable it above if you "
                "have rights to the audio."
            )

        convert_clicked = st.button("Convert to tab PDF", type="secondary")

        if convert_clicked:
            if not uploaded and not youtube_url.strip() and not using_carry_over:
                st.error("Upload an audio file or enter a YouTube URL.")
                return
            if youtube_url.strip() and not is_youtube_url(youtube_url):
                st.error("Only YouTube URLs are allowed.")
                return

            effective_separate = separate_stems and demucs_ok
            skipped_separation = separate_stems and not demucs_ok

            output_dir = run_output_dir()
            config = PipelineConfig(
                separate_stems=effective_separate,
                max_duration_sec=max_duration,
                title=title or "Guitar Tab",
                mix_aware_filtering=mix_aware,
                onset_threshold=onset_threshold,
                frame_threshold=frame_threshold,
                tempo_bpm_override=tempo_override if tempo_override > 0 else None,
            )

            # Known, fixed stage order the pipeline reports via on_progress — used only to
            # render an approximate step-based progress bar (no percentage is available).
            stage_order = (
                ["ingest", "separate", "transcribe", "tempo", "tab", "pdf", "done"]
                if effective_separate
                else ["ingest", "transcribe", "tempo", "tab", "pdf", "done"]
            )

            try:
                with st.status("Starting…", expanded=True) as status:
                    progress_bar = st.progress(0.0)

                    def on_progress(stage: str, message: str) -> None:
                        status.update(label=f"[{stage}] {message}")
                        if stage in stage_order:
                            progress_bar.progress(
                                (stage_order.index(stage) + 1) / len(stage_order)
                            )

                    if uploaded:
                        audio_path = save_upload(uploaded)
                    elif using_carry_over:
                        audio_path = Path(carry_over_path)
                    else:
                        audio_path = None
                    url = youtube_url.strip() or None

                    artifacts = run_pipeline(
                        audio_path=audio_path,
                        youtube_url=url,
                        output_dir=output_dir,
                        config=config,
                        on_progress=on_progress,
                    )

                st.session_state["tab_pdf_artifacts"] = {
                    k: str(v) for k, v in artifacts.items()
                }
                st.session_state["tab_pdf_title"] = title or "Guitar Tab"
                st.session_state["tab_pdf_skipped_separation"] = skipped_separation
                st.session_state["tab_pdf_source_audio_path"] = (
                    str(audio_path) if audio_path else None
                )
                st.session_state["tab_pdf_flash"] = "Conversion complete."
                write_run_metadata(
                    output_dir,
                    page="tab_pdf",
                    title=title or "Guitar Tab",
                    artifacts=artifacts,
                )
                # Consumed — clear so it doesn't linger for unrelated future conversions.
                st.session_state.pop("carry_over_audio_path", None)
                st.session_state.pop("carry_over_audio_name", None)
                # Rerun so Conversion settings collapses and results sit near the top.
                st.rerun()

            except Exception as exc:
                st.error(
                    "Conversion failed — your file and settings are still here, "
                    "so you can just try again."
                )
                with st.expander("Technical details"):
                    st.code(str(exc))

    artifacts_map = st.session_state.get("tab_pdf_artifacts")
    if not artifacts_map:
        return

    if flash := st.session_state.pop("tab_pdf_flash", None):
        st.success(flash)

    result_title = st.session_state.get("tab_pdf_title", "Guitar Tab")
    st.subheader(result_title)
    st.caption("Demo output — check every note before you trust or share it.")
    if st.session_state.get("tab_pdf_skipped_separation"):
        st.info(
            "Ran without stem separation — install Demucs for better full-mix results. "
            f"{DEMUCS_INSTALL_HINT}"
        )

    pdf_path = Path(artifacts_map["pdf"])
    tab_path = Path(artifacts_map["tab"])
    midi_path = Path(artifacts_map["midi"])

    st.download_button(
        label="Download PDF",
        data=pdf_path.read_bytes(),
        file_name=f"{result_title or 'guitar_tab'}.pdf",
        mime="application/pdf",
        type="primary",
    )
    with st.expander("Other downloads"):
        st.download_button(
            label="Download ASCII tab (.tab)",
            data=tab_path.read_text(encoding="utf-8"),
            file_name=f"{result_title or 'guitar_tab'}.tab",
            mime="text/plain",
        )
        st.download_button(
            label="Download MIDI (.mid)",
            data=midi_path.read_bytes(),
            file_name=f"{result_title or 'guitar_tab'}.mid",
            mime="audio/midi",
        )
        stem_path_str = artifacts_map.get("guitar_stem")
        stem_path = Path(stem_path_str) if stem_path_str else None
        if stem_path and stem_path.exists():
            st.download_button(
                label="Download guitar stem (.wav)",
                data=stem_path.read_bytes(),
                file_name=f"{result_title or 'guitar_tab'}_guitar_stem.wav",
                mime="audio/wav",
            )

    source_audio_path = st.session_state.get("tab_pdf_source_audio_path")
    if source_audio_path and Path(source_audio_path).exists():
        if st.button("Separate this in Audio Isolation →", type="primary"):
            st.session_state["carry_over_audio_path"] = source_audio_path
            st.session_state["carry_over_audio_name"] = Path(source_audio_path).name
            st.switch_page(str(Path(__file__).with_name("isolate.py")))


main()
