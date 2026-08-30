"""End-to-end audio to tab PDF pipeline."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from audio_to_tab.ingest import download_youtube_audio, normalize_audio
from audio_to_tab.isolate import analyze_guitar_stem_quality
from audio_to_tab.midi_cleanup import (
    CleanupConfig,
    mix_aware_cleanup_config,
    solo_guitar_cleanup_config,
)
from audio_to_tab.pdf_render import render_structured_tab_pdf
from audio_to_tab.rhythm import quantize_tab_document
from audio_to_tab.separate import separate_guitar_stem
from audio_to_tab.tab_generate import midi_to_tab, tab_to_ascii
from audio_to_tab.tempo import resolve_tempo
from audio_to_tab.transcribe import transcribe_audio

YOUTUBE_DISCLAIMER = (
    "YouTube audio download may violate YouTube Terms of Service. "
    "You are responsible for ensuring you have rights to transcribe the material."
)

DEMUCS_INSTALL_HINT = (
    "Demucs is required for stem separation. Install with: make install-demucs "
    "or pip install -e \".[demucs]\""
)


@dataclass
class PipelineConfig:
    separate_stems: bool = True
    demucs_quality: str = "balanced"
    demucs_device: str = "cpu"
    model: str = "htdemucs_6s"
    guitar_checkpoint: str | None = None
    guitar_refine: bool = False
    demucs_segment: int | None = 8
    demucs_jobs: int = 1
    fold_other_mode: str | None = None
    low_end_restore_db: float = 0.0
    sub_bass_debleed: bool = False
    bleed_gate: bool = False
    adaptive_fold_gain: bool = False
    guitar_ensemble: bool = False
    mix_aware_filtering: bool = True
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    minimum_note_length_ms: float = 58.0
    min_velocity: int = 40
    min_duration_sec: float = 0.05
    quantize_sec: float | None = 0.05
    max_notes_per_onset: int = 6
    max_duration_sec: float | None = None
    title: str = "Guitar Tab"
    tempo_bpm_override: float | None = None
    beats_per_measure: int = 4


ProgressCallback = Callable[[str, str], None]  # stage, message


def _noop_progress(stage: str, message: str) -> None:
    pass


def _separate_progress_label(cfg: PipelineConfig) -> str:
    model = (cfg.model or "htdemucs_6s").lower()
    if model in {"bs_roformer_sw", "melband_roformer_guitar"}:
        return "Isolating guitar stem with BS-RoFormer"
    if model in {"guitar_scnet"}:
        return "Isolating guitar stem with SCNet"
    if cfg.guitar_checkpoint:
        return "Isolating guitar stem with guitar-ft Demucs"
    return "Isolating guitar stem"


def _trim_audio(input_path: Path, max_duration_sec: float | None) -> Path:
    if max_duration_sec is None or max_duration_sec <= 0:
        return input_path
    import subprocess

    from audio_to_tab.subprocess_util import subprocess_run_kwargs

    out = input_path.parent / f"{input_path.stem}_trim.wav"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return input_path
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(input_path), "-t", str(max_duration_sec), str(out)],
        capture_output=True,
        check=False,
        **subprocess_run_kwargs(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg trim failed: {result.stderr or result.stdout}")
    return out


def _cleanup_config_for_pipeline(cfg: PipelineConfig) -> CleanupConfig:
    base = mix_aware_cleanup_config() if cfg.mix_aware_filtering else solo_guitar_cleanup_config()
    return CleanupConfig(
        min_velocity=cfg.min_velocity if not cfg.mix_aware_filtering else max(cfg.min_velocity, base.min_velocity),
        min_duration_sec=cfg.min_duration_sec if not cfg.mix_aware_filtering else max(cfg.min_duration_sec, base.min_duration_sec),
        quantize_sec=cfg.quantize_sec,
        max_notes_per_onset=cfg.max_notes_per_onset,
    )


def _transcription_thresholds(cfg: PipelineConfig) -> tuple[float, float, float]:
    onset = cfg.onset_threshold
    frame = cfg.frame_threshold
    min_len = cfg.minimum_note_length_ms
    if cfg.mix_aware_filtering:
        onset = max(onset, 0.58)
        frame = max(frame, 0.40)
        min_len = max(min_len, 90.0)
    return onset, frame, min_len


def run_pipeline(
    *,
    audio_path: Path | None = None,
    youtube_url: str | None = None,
    output_dir: Path,
    config: PipelineConfig | None = None,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Path]:
    """
    Run full pipeline: ingest → [separate] → transcribe → tab → PDF.

    Returns paths to midi, tab txt, and pdf artifacts.
    """
    cfg = config or PipelineConfig()
    progress = on_progress or _noop_progress
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # --- Ingest ---
        progress("ingest", "Loading audio")
        if youtube_url:
            progress("ingest", YOUTUBE_DISCLAIMER)
            raw_audio = download_youtube_audio(youtube_url, tmp_path)
        elif audio_path:
            raw_audio = normalize_audio(audio_path, tmp_path / "normalized.wav")
        else:
            raise ValueError("Provide audio_path or youtube_url")

        work_audio = _trim_audio(raw_audio, cfg.max_duration_sec)

        # --- Separate (optional) ---
        transcribe_input = work_audio
        tempo_audio_source = work_audio
        if cfg.separate_stems:
            progress("separate", _separate_progress_label(cfg))
            stem_path = output_dir / "guitar_stem.wav"
            try:
                recovery_diag_path = (
                    output_dir / "low_end_recovery_diagnostics.json"
                    if cfg.sub_bass_debleed or cfg.low_end_restore_db
                    else None
                )
                separate_guitar_stem(
                    work_audio,
                    stem_path,
                    model=cfg.model,
                    device=cfg.demucs_device,
                    quality=cfg.demucs_quality,
                    demucs_segment=cfg.demucs_segment,
                    demucs_jobs=cfg.demucs_jobs,
                    guitar_refine=cfg.guitar_refine,
                    guitar_checkpoint=cfg.guitar_checkpoint,
                    fold_other_mode=cfg.fold_other_mode,
                    sub_bass_debleed=cfg.sub_bass_debleed,
                    low_end_restore_db=cfg.low_end_restore_db,
                    bleed_gate=cfg.bleed_gate,
                    adaptive_fold_gain=cfg.adaptive_fold_gain,
                    guitar_ensemble=cfg.guitar_ensemble,
                    recovery_diagnostics_path=recovery_diag_path,
                    bleed_gate_diagnostics_path=(
                        output_dir / "bleed_gate_diagnostics.json"
                        if cfg.bleed_gate
                        else None
                    ),
                )
                quality_diag = analyze_guitar_stem_quality(stem_path)
                quality_diag.write_json(output_dir / "guitar_stem_quality.json")
                transcribe_input = stem_path
                tempo_audio_source = stem_path
            except (RuntimeError, FileNotFoundError) as exc:
                raise RuntimeError(
                    f"Guitar stem separation failed: {exc}. "
                    f"For solo guitar, disable separation. {DEMUCS_INSTALL_HINT}"
                ) from exc

        # --- Transcribe ---
        progress("transcribe", "Detecting notes with Basic Pitch")
        midi_path = output_dir / "transcription.mid"
        onset_th, frame_th, min_len_ms = _transcription_thresholds(cfg)
        transcribe_audio(
            transcribe_input,
            midi_path,
            onset_threshold=onset_th,
            frame_threshold=frame_th,
            minimum_note_length_ms=min_len_ms,
            cleanup=_cleanup_config_for_pipeline(cfg),
            normalize=False,
        )

        # --- Tempo ---
        progress("tempo", "Estimating tempo")
        tempo_est = resolve_tempo(
            audio_path=tempo_audio_source,
            midi_path=midi_path,
            override_bpm=cfg.tempo_bpm_override,
        )

        # --- Tab ---
        progress("tab", "Assigning frets and generating tab")
        tab_doc = midi_to_tab(
            str(midi_path),
            tempo_bpm=tempo_est.bpm,
            tempo_confidence=tempo_est.confidence,
            beats_per_measure=cfg.beats_per_measure,
        )
        tab_doc = quantize_tab_document(tab_doc, beats_per_measure=cfg.beats_per_measure)
        tab_txt_path = output_dir / "transcription.tab"
        tab_txt_path.write_text(tab_to_ascii(tab_doc), encoding="utf-8")

        # --- PDF ---
        progress("pdf", "Rendering PDF")
        pdf_path = output_dir / "transcription.pdf"
        render_structured_tab_pdf(tab_doc, str(pdf_path), title=cfg.title)

        progress("done", "Pipeline complete")

        artifacts: dict[str, Path] = {
            "midi": midi_path,
            "tab": tab_txt_path,
            "pdf": pdf_path,
        }
        if cfg.separate_stems and (output_dir / "guitar_stem.wav").exists():
            artifacts["guitar_stem"] = output_dir / "guitar_stem.wav"

        return artifacts
