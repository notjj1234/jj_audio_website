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
from audio_to_tab.ingest import YouTubeDownloadError, is_youtube_url  # noqa: E402
from audio_to_tab.roformer import is_roformer_backend_available  # noqa: E402
from audio_to_tab.separate import guitar_ft_weights_path, is_demucs_available  # noqa: E402
from ui.isolate_state import (  # noqa: E402
    TRACK_OPTIONS,
    default_guitar_track_option,
    guitar_track_radio_ids,
    normalize_guitar_track_selection,
)


def main() -> None:
    st.title("Tab PDF (demo)")
    st.error(
        "**JJs stuff — NOT A FINISHED PRODUCT**. Tab PDF barely works. "
        "Tabs are 90% wrong and or unusable. This page is here so I can experiment with it."
    )
    st.warning(
        "Best on short solo-guitar clips. For full songs, isolate guitar first on "
        "**Audio Isolation**."
    )

    demucs_ok = is_demucs_available()
    roformer_ok = is_roformer_backend_available()
    guitar_ft_ok = guitar_ft_weights_path().is_file()
    can_separate = demucs_ok or roformer_ok
    if not can_separate:
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
            "Separate guitar stem — required for full mixes",
            value=can_separate,
            disabled=not can_separate,
            help=(
                "Turn off for solo guitar uploads (much faster). "
                "Install Demucs to enable: make install-demucs"
                if not can_separate
                else "Turn off only for solo guitar uploads (much faster)."
            ),
        )
        tab_model = "htdemucs_6s"
        tab_guitar_refine = False
        tab_guitar_checkpoint = None
        tab_low_end_restore_db = 0.0
        tab_sub_bass_debleed = False
        tab_bleed_gate = False
        tab_adaptive_fold_gain = False
        tab_guitar_ensemble = False
        if separate_stems and can_separate:
            if "tab_low_end_restore_db" not in st.session_state:
                st.session_state["tab_low_end_restore_db"] = 0.0
            if "tab_sub_bass_debleed" not in st.session_state:
                st.session_state["tab_sub_bass_debleed"] = False
            radio_ids = guitar_track_radio_ids(roformer_available=roformer_ok)
            guitar_labels = {
                oid: TRACK_OPTIONS[oid]["label"] if oid in TRACK_OPTIONS else oid
                for oid in radio_ids
                if oid != "none"
            }
            promoted_default = default_guitar_track_option(
                roformer_available=roformer_ok
            )
            current_engine = str(
                st.session_state.get("tab_guitar_engine") or promoted_default
            )
            if current_engine not in guitar_labels:
                st.session_state["tab_guitar_engine"] = normalize_guitar_track_selection(
                    current_engine,
                    roformer_available=roformer_ok,
                )
                if st.session_state["tab_guitar_engine"] not in guitar_labels:
                    st.session_state["tab_guitar_engine"] = next(iter(guitar_labels))
            engine = st.radio(
                "Guitar separation",
                options=list(guitar_labels.keys()),
                format_func=lambda oid: guitar_labels[oid],
                key="tab_guitar_engine",
            )
            if engine == "guitar_roformer":
                tab_model = "bs_roformer_sw"
            elif engine == "guitar_roformer_refine":
                tab_model = "bs_roformer_sw"
                tab_guitar_refine = True
            else:
                tab_model = "htdemucs_6s"
            if tab_model == "htdemucs_6s":
                if guitar_ft_ok:
                    if st.checkbox(
                        "Use cached guitar-ft Demucs weights",
                        value=False,
                        key="tab_guitar_ft",
                        help="Uses guitar-ft already in TORCH_HOME. Does not download.",
                    ):
                        tab_guitar_checkpoint = "htdemucs_6s_guitar_ft"
                else:
                    st.caption(
                        "guitar-ft is available after a one-time ~330 MB download from "
                        "Audio Isolation → Advanced."
                    )
            tab_low_end_restore_db = float(
                st.slider(
                    "Low-end restore (dB)",
                    min_value=0.0,
                    max_value=6.0,
                    step=1.0,
                    key="tab_low_end_restore_db",
                    help=(
                        "Boosts 60–200 Hz on the guitar stem before transcription. "
                        "0 = off. Opt-in; changes A/B scores."
                    ),
                )
            )
            tab_sub_bass_debleed = st.checkbox(
                "Subtractive bass de-bleed",
                key="tab_sub_bass_debleed",
                help=(
                    "Subtracts scaled bass/drum energy below ~150 Hz from the guitar stem "
                    "before transcription. Opt-in; default off."
                ),
            )
            tab_bleed_gate = st.checkbox(
                "Spectral bleed gate",
                key="tab_bleed_gate",
                help=(
                    "Scrubs leftover bass/cymbal flutter from the guitar stem when the "
                    "separator's competitor stems dominate it. Opt-in; default off."
                ),
            )
            tab_adaptive_fold_gain = st.checkbox(
                "Adaptive fold gain",
                key="tab_adaptive_fold_gain",
                help=(
                    "Searches the Other→Guitar mix gain instead of the fixed 0.5. "
                    "Opt-in; default off."
                ),
            )
            tab_guitar_ensemble = st.checkbox(
                "Cross-model guitar ensemble",
                key="tab_guitar_ensemble",
                help=(
                    "Also runs BS-RoFormer-SW and per-band blends the two guitar "
                    "stems. Much slower; requires the [roformer] extra; opt-in "
                    "(default off)."
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
            value=False,
            help=(
                "Off by default. Enable only if you have rights to the audio. "
                "Arbitrary URLs are rejected."
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

            effective_separate = separate_stems and can_separate
            skipped_separation = separate_stems and not can_separate

            output_dir = run_output_dir()
            config = PipelineConfig(
                separate_stems=effective_separate,
                max_duration_sec=max_duration,
                title=title or "Guitar Tab",
                mix_aware_filtering=mix_aware,
                onset_threshold=onset_threshold,
                frame_threshold=frame_threshold,
                tempo_bpm_override=tempo_override if tempo_override > 0 else None,
                model=tab_model,
                guitar_refine=tab_guitar_refine,
                guitar_checkpoint=tab_guitar_checkpoint,
                low_end_restore_db=tab_low_end_restore_db,
                sub_bass_debleed=tab_sub_bass_debleed,
                bleed_gate=tab_bleed_gate,
                adaptive_fold_gain=tab_adaptive_fold_gain,
                guitar_ensemble=tab_guitar_ensemble,
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

            except YouTubeDownloadError as exc:
                st.error(str(exc))
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


if __name__ == "__main__":
    main()
