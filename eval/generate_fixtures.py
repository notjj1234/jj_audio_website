"""Generate synthetic evaluation fixtures (MIDI + optional WAV)."""

from __future__ import annotations

import json
import subprocess
import shutil
from pathlib import Path

import numpy as np
import pretty_midi


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _make_melody_notes() -> list[tuple[int, float, float]]:
    """Twinkle-style monophonic melody on high E string frets."""
    # (pitch, start, duration)
    sequence = [
        (64, 0.0, 0.4),   # E4 open
        (64, 0.5, 0.4),
        (67, 1.0, 0.4),   # G4
        (67, 1.5, 0.4),
        (69, 2.0, 0.4),   # A4
        (69, 2.5, 0.4),
        (67, 3.0, 0.8),   # G4
        (65, 4.0, 0.4),   # F4
        (65, 4.5, 0.4),
        (64, 5.0, 0.4),
        (64, 5.5, 0.4),
        (62, 6.0, 0.4),   # D4
        (62, 6.5, 0.4),
        (64, 7.0, 0.8),
    ]
    return sequence


def _make_arpeggio_notes() -> list[tuple[int, float, float]]:
    """C major arpeggio fingerpicked."""
    notes = []
    t = 0.0
    for pitch in (48, 52, 55, 60, 55, 52):  # C3 E3 G3 C4 G3 E3
        notes.append((pitch, t, 0.35))
        t += 0.4
    for pitch in (48, 52, 55, 64, 55, 52):
        notes.append((pitch, t, 0.35))
        t += 0.4
    return notes


def _make_chord_notes() -> list[tuple[int, float, float]]:
    """Simple strummed G and C chords."""
    chords = [
        ([47, 50, 55, 59], 0.0),   # G chord voicing
        ([48, 52, 55, 60], 2.0),   # C chord
        ([47, 50, 55, 59], 4.0),
    ]
    notes = []
    for pitches, start in chords:
        for p in pitches:
            notes.append((p, start, 1.5))
    return notes


def _write_midi(path: Path, note_data: list[tuple[int, float, float]], tempo: int = 120) -> None:
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    guitar = pretty_midi.Instrument(program=25, name="Acoustic Guitar")
    for pitch, start, dur in note_data:
        guitar.notes.append(
            pretty_midi.Note(velocity=90, pitch=pitch, start=start, end=start + dur)
        )
    pm.instruments.append(guitar)
    pm.write(str(path))


def _synthesize_wav_numpy(midi_path: Path, wav_path: Path) -> bool:
    """Fallback: synthesize simple sine tones from MIDI notes."""
    try:
        import numpy as np
        import soundfile as sf
        import pretty_midi

        pm = pretty_midi.PrettyMIDI(str(midi_path))
        sr = 44100
        duration = max(pm.get_end_time(), 1.0)
        audio = np.zeros(int(duration * sr) + sr)
        for inst in pm.instruments:
            for note in inst.notes:
                start = int(note.start * sr)
                end = int(note.end * sr)
                length = max(end - start, 1)
                t = np.arange(length) / sr
                freq = pretty_midi.note_number_to_hz(note.pitch)
                tone = 0.25 * np.sin(2 * np.pi * freq * t)
                audio[start : start + length] += tone
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.8
        sf.write(str(wav_path), audio, sr)
        return True
    except Exception:
        return False


def _synthesize_wav(midi_path: Path, wav_path: Path) -> bool:
    """Synthesize MIDI to WAV using fluidsynth if available, else numpy fallback."""
    fluidsynth = shutil.which("fluidsynth")
    if fluidsynth:
        sf2_candidates = [
            Path(pretty_midi.__file__).parent / "TimGM6mb.sf2",
        ]
        sf2 = next((p for p in sf2_candidates if p.exists()), None)
        if sf2 is not None:
            cmd = [
                fluidsynth,
                "-ni",
                str(sf2),
                str(midi_path),
                "-F",
                str(wav_path),
                "-r",
                "44100",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and wav_path.exists():
                return True
    return _synthesize_wav_numpy(midi_path, wav_path)


def generate_all_fixtures() -> list[dict]:
    """Create MIDI fixtures and synthesize WAV where fluidsynth is available."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    fixtures = [
        {"id": "solo_melody", "notes": _make_melody_notes(), "category": "monophonic"},
        {"id": "arpeggio", "notes": _make_arpeggio_notes(), "category": "fingerpicked"},
        {"id": "chords", "notes": _make_chord_notes(), "category": "polyphonic"},
    ]

    manifest = []
    for fx in fixtures:
        fid = fx["id"]
        midi_path = FIXTURES_DIR / f"{fid}.mid"
        wav_path = FIXTURES_DIR / f"{fid}.wav"
        _write_midi(midi_path, fx["notes"])
        has_wav = _synthesize_wav(midi_path, wav_path)
        entry = {
            "id": fid,
            "category": fx["category"],
            "midi": str(midi_path.relative_to(FIXTURES_DIR.parent)),
            "wav": str(wav_path.relative_to(FIXTURES_DIR.parent)) if has_wav else None,
            "note_count": len(fx["notes"]),
        }
        manifest.append(entry)

    manifest_path = FIXTURES_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    items = generate_all_fixtures()
    for item in items:
        wav_status = "wav ok" if item["wav"] else "midi only (install fluidsynth for wav)"
        print(f"  {item['id']}: {item['note_count']} notes — {wav_status}")
