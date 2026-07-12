"""Audio transcription via Spotify Basic Pitch."""

from __future__ import annotations

import tempfile
from pathlib import Path

from basic_pitch import ICASSP_2022_MODEL_PATH
from basic_pitch.inference import predict

from audio_to_tab.ingest import normalize_audio
from audio_to_tab.midi_cleanup import CleanupConfig, cleanup_midi, merge_instruments_to_one


def transcribe_audio(
    audio_path: str | Path,
    output_midi_path: str | Path,
    *,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    minimum_note_length_ms: float = 58.0,
    cleanup: CleanupConfig | None = None,
    normalize: bool = True,
) -> Path:
    """Run Basic Pitch on audio and write cleaned MIDI."""
    audio_path = Path(audio_path)
    output_path = Path(output_midi_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_audio = normalize_audio(audio_path) if normalize else audio_path

    with tempfile.TemporaryDirectory() as tmp:
        _, midi_data, _ = predict(
            str(work_audio),
            model_or_model_path=ICASSP_2022_MODEL_PATH,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=minimum_note_length_ms,
        )

        raw_path = Path(tmp) / "raw.mid"
        midi_data.write(str(raw_path))

        cleaned_tmp = Path(tmp) / "cleaned.mid"
        cleanup_midi(str(raw_path), str(cleaned_tmp), config=cleanup)

        pm = merge_instruments_to_one(__import__("pretty_midi").PrettyMIDI(str(cleaned_tmp)))
        pm.write(str(output_path))

    if normalize and work_audio != audio_path and work_audio.exists():
        try:
            work_audio.unlink()
        except OSError:
            pass

    return output_path
