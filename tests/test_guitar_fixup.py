"""Tests for post-separation mixer guitar fix-up."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from audio_to_tab.isolate import analyze_bass_bleed
from ui.guitar_fixup import (
    GUITAR_BACKUP_NAME,
    apply_mixer_guitar_fixup,
    ensure_guitar_backup,
    has_guitar_backup,
    reset_mixer_guitar_fixup,
)


def _write_bleed_fixture(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    sr = 22050
    seconds = 0.4
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    guitar_tone = 0.12 * np.sin(2 * np.pi * 82.0 * t) + 0.18 * np.sin(2 * np.pi * 2000.0 * t)
    bass_tone = 0.45 * np.sin(2 * np.pi * 55.0 * t)
    bled = (guitar_tone + 0.7 * bass_tone).astype(np.float32)
    bass_only = bass_tone.astype(np.float32)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    guitar = run_dir / "guitar.wav"
    bass = run_dir / "bass.wav"
    sf.write(str(guitar), bled, sr)
    sf.write(str(bass), bass_only, sr)
    stem_paths = {"guitar": guitar, "bass": bass}
    return run_dir, stem_paths


def test_ensure_guitar_backup_creates_original_copy(tmp_path: Path):
    run_dir, stem_paths = _write_bleed_fixture(tmp_path)
    guitar = stem_paths["guitar"]
    backup = ensure_guitar_backup(guitar)
    assert backup.name == GUITAR_BACKUP_NAME
    assert has_guitar_backup(guitar)
    assert backup.read_bytes() == guitar.read_bytes()


def test_apply_mixer_guitar_fixup_reduces_bass_heavy_share(tmp_path: Path):
    run_dir, stem_paths = _write_bleed_fixture(tmp_path)
    guitar = stem_paths["guitar"]
    before = analyze_bass_bleed(guitar).low_band_energy_share
    assert before is not None and before >= 0.65

    result = apply_mixer_guitar_fixup(
        guitar_path=guitar,
        stem_paths=stem_paths,
        run_dir=run_dir,
        sub_bass_debleed=True,
        low_end_restore_db=0.0,
    )
    assert result.ok is True
    after = analyze_bass_bleed(guitar).low_band_energy_share
    assert after is not None
    assert after < before
    assert (run_dir / "bass_bleed_diagnostics.json").is_file()
    assert (run_dir / "low_end_recovery_diagnostics.json").is_file()


def test_reset_mixer_guitar_fixup_restores_backup(tmp_path: Path):
    run_dir, stem_paths = _write_bleed_fixture(tmp_path)
    guitar = stem_paths["guitar"]
    original_bytes = guitar.read_bytes()

    apply_mixer_guitar_fixup(
        guitar_path=guitar,
        stem_paths=stem_paths,
        run_dir=run_dir,
        sub_bass_debleed=True,
        low_end_restore_db=0.0,
    )
    assert guitar.read_bytes() != original_bytes

    reset = reset_mixer_guitar_fixup(
        guitar_path=guitar,
        stem_paths=stem_paths,
        run_dir=run_dir,
    )
    assert reset.ok is True
    assert guitar.read_bytes() == original_bytes


def test_apply_mixer_guitar_fixup_requires_enabled_stage(tmp_path: Path):
    run_dir, stem_paths = _write_bleed_fixture(tmp_path)
    result = apply_mixer_guitar_fixup(
        guitar_path=stem_paths["guitar"],
        stem_paths=stem_paths,
        run_dir=run_dir,
        sub_bass_debleed=False,
        low_end_restore_db=0.0,
    )
    assert result.ok is False
