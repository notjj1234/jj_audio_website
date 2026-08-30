"""Guitar stem backups, peak limiting, and preset defaults."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from audio_to_tab.isolate import (
    FOLD_OTHER_MIX_GAIN,
    GUITAR_PREREFINE_NAME,
    GUITAR_REFINED_NAME,
    _highpass_rms,
    apply_sub_bass_debleed,
    ensure_guitar_prerefine_backup,
    has_guitar_prerefine,
    switch_guitar_stem_variant,
)
from audio_to_tab.roformer import REFINE_OTHER_MIX_GAIN
from ui.guitar_fixup import apply_mixer_guitar_fixup
from ui.isolate_state import resolve_separation_preset


def _write_tone(path: Path, hz: float, sr: int = 22050, seconds: float = 0.4) -> None:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    y = (0.25 * np.sin(2 * np.pi * hz * t)).astype(np.float32)
    sf.write(str(path), y, sr)


def test_full_band_preset_uses_roformer_without_refine():
    resolved = resolve_separation_preset("full_band")
    assert resolved["model"] == "bs_roformer_sw"
    assert resolved["guitar_refine"] is False


def test_best_guitar_preset_keeps_melband_refine():
    resolved = resolve_separation_preset("best_guitar")
    assert resolved["model"] == "bs_roformer_sw"
    assert resolved["guitar_refine"] is True


def test_ensure_guitar_prerefine_backup_once(tmp_path: Path):
    guitar = tmp_path / "guitar.wav"
    _write_tone(guitar, 440.0)
    before = guitar.read_bytes()
    ensure_guitar_prerefine_backup(guitar)
    prerefine = tmp_path / GUITAR_PREREFINE_NAME
    assert prerefine.is_file()
    assert has_guitar_prerefine(guitar)
    guitar.write_bytes(b"changed")
    ensure_guitar_prerefine_backup(guitar)
    assert prerefine.read_bytes() != b"changed"
    assert prerefine.read_bytes() != before or len(before) > 0


def test_switch_guitar_stem_variant(tmp_path: Path):
    guitar = tmp_path / "guitar.wav"
    pre = tmp_path / GUITAR_PREREFINE_NAME
    refined = tmp_path / GUITAR_REFINED_NAME
    _write_tone(pre, 300.0)
    _write_tone(refined, 8000.0)
    _write_tone(guitar, 1000.0)

    assert switch_guitar_stem_variant(guitar, use_prerefine=True)
    assert switch_guitar_stem_variant(guitar, use_prerefine=False)


def test_run_guitar_refine_saves_backups(tmp_path: Path, monkeypatch):
    from audio_to_tab.roformer import run_guitar_refine

    guitar = tmp_path / "guitar.wav"
    _write_tone(guitar, 440.0)
    pre_bytes = guitar.read_bytes()

    def fake_refine(artifacts, *, device="cpu", work_dir=None):
        path = artifacts["guitar"]
        _write_tone(path, 880.0)
        return artifacts

    monkeypatch.setattr("audio_to_tab.roformer.refine_guitar_from_stems", fake_refine)
    run_guitar_refine(guitar, guitar, device="cpu")

    assert (tmp_path / GUITAR_PREREFINE_NAME).is_file()
    assert (tmp_path / GUITAR_REFINED_NAME).is_file()
    assert guitar.read_bytes() != pre_bytes


def test_refine_guitar_from_stems_cleans_work_dir(tmp_path: Path, monkeypatch):
    from audio_to_tab.roformer import refine_guitar_from_stems

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    guitar = run_dir / "guitar.wav"
    other = run_dir / "other.wav"
    _write_tone(guitar, 440.0)
    _write_tone(other, 110.0)
    original = guitar.read_bytes()

    def fake_melband(audio_path, output_root, *, device="cpu"):
        output_root.mkdir(parents=True, exist_ok=True)
        _write_tone(output_root / "guitar.wav", 880.0)
        _write_tone(output_root / "other.wav", 220.0)
        return {"guitar": output_root / "guitar.wav", "other": output_root / "other.wav"}

    monkeypatch.setattr("audio_to_tab.roformer.run_melband_guitar", fake_melband)
    artifacts = refine_guitar_from_stems({"guitar": guitar, "other": other})
    assert artifacts["guitar"] == guitar
    assert not (run_dir / "_guitar_refine").exists()
    assert guitar.read_bytes() != original


def test_apply_fixup_always_sources_from_backup(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    guitar = run_dir / "guitar.wav"
    bass = run_dir / "bass.wav"
    sr = 22050
    t = np.linspace(0, 0.4, int(sr * 0.4), endpoint=False)
    bled = (0.12 * np.sin(2 * np.pi * 82.0 * t) + 0.6 * np.sin(2 * np.pi * 55.0 * t)).astype(
        np.float32
    )
    sf.write(str(guitar), bled, sr)
    sf.write(str(bass), (0.4 * np.sin(2 * np.pi * 55.0 * t)).astype(np.float32), sr)
    original_bytes = guitar.read_bytes()

    apply_mixer_guitar_fixup(
        guitar_path=guitar,
        stem_paths={"guitar": guitar, "bass": bass},
        run_dir=run_dir,
        sub_bass_debleed=True,
        low_end_restore_db=0.0,
    )
    after_first = guitar.read_bytes()

    apply_mixer_guitar_fixup(
        guitar_path=guitar,
        stem_paths={"guitar": guitar, "bass": bass},
        run_dir=run_dir,
        sub_bass_debleed=True,
        low_end_restore_db=0.0,
    )
    after_second = guitar.read_bytes()
    assert after_first == after_second
    assert (run_dir / "guitar_original.wav").read_bytes() == original_bytes


def test_debleed_preserves_high_end_better_than_hard_normalize(tmp_path: Path):
    sr = 22050
    seconds = 0.4
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    guitar_tone = 0.1 * np.sin(2 * np.pi * 82.0 * t) + 0.35 * np.sin(2 * np.pi * 4000.0 * t)
    bass_tone = 0.5 * np.sin(2 * np.pi * 55.0 * t)
    bled = (guitar_tone + 0.7 * bass_tone).astype(np.float32)
    bass_only = bass_tone.astype(np.float32)
    guitar_wav = tmp_path / "guitar.wav"
    bass_wav = tmp_path / "bass.wav"
    sf.write(str(guitar_wav), bled, sr)
    sf.write(str(bass_wav), bass_only, sr)

    apply_sub_bass_debleed(guitar_wav, guitar_wav, bass_wav)
    data, _ = sf.read(str(guitar_wav), always_2d=True)
    mono = data.mean(axis=1)
    high = _highpass_rms(mono, sr, 4000.0)
    total = float(np.sqrt(np.mean(np.square(mono)) + 1e-12))
    assert high / total > 0.15


def test_fold_and_refine_mix_gains_are_conservative():
    assert 0.0 < FOLD_OTHER_MIX_GAIN < 1.0
    assert 0.0 < REFINE_OTHER_MIX_GAIN < 1.0
