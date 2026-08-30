"""Opt-in guitar improvements: spectral bleed gate, adaptive fold gain, ensemble."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.isolate import (
    FOLD_OTHER_GAIN_CANDIDATES,
    IsolateConfig,
    apply_bleed_gate,
    apply_fold_other_gain_search,
    apply_fold_other_into_guitar,
    blend_guitar_stems,
    isolate_timeout_multiplier,
)

SR = 44100


def _tone_wav(path: Path, freq: float, amp: float = 0.2, seconds: float = 0.1) -> Path:
    t = np.arange(int(SR * seconds), dtype=np.float64) / SR
    y = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.column_stack([y, y]), SR, subtype="PCM_16")
    return path


def test_bleed_gate_noop_when_guitar_dominates(tmp_path: Path):
    rng = np.random.default_rng(7)
    t = np.arange(int(SR * 0.1), dtype=np.float64) / SR
    guitar_y = (0.5 * rng.standard_normal(len(t))).astype(np.float32)
    bass_y = (0.001 * rng.standard_normal(len(t))).astype(np.float32)
    guitar = tmp_path / "guitar.wav"
    bass = tmp_path / "bass.wav"
    sf.write(str(guitar), np.column_stack([guitar_y, guitar_y]), SR, subtype="PCM_16")
    sf.write(str(bass), np.column_stack([bass_y, bass_y]), SR, subtype="PCM_16")
    before = sf.read(str(guitar))[0].copy()
    diag = apply_bleed_gate(guitar, competitor_paths={"bass": bass})
    assert diag.attempted is True
    assert diag.gated is False
    assert "nothing" in diag.reason
    after = sf.read(str(guitar))[0]
    assert np.array_equal(before, after)


def test_bleed_gate_scrubs_dominated_bins(tmp_path: Path):
    guitar = _tone_wav(tmp_path / "guitar.wav", 440.0, amp=0.001)
    bass = _tone_wav(tmp_path / "bass.wav", 55.0, amp=0.5)
    out = tmp_path / "gated.wav"
    diag = apply_bleed_gate(
        guitar,
        out,
        competitor_paths={"bass": bass},
        threshold=0.8,
        max_attenuation_linear=0.25,
    )
    assert diag.attempted is True
    assert diag.gated is True
    assert diag.mean_attenuation_db > 0.0
    in_data = sf.read(str(guitar))[0]
    out_data = sf.read(str(out))[0]
    assert np.sqrt(np.mean(np.square(out_data))) < np.sqrt(np.mean(np.square(in_data)))


def test_bleed_gate_missing_competitors_not_attempted(tmp_path: Path):
    guitar = _tone_wav(tmp_path / "guitar.wav", 440.0)
    diag = apply_bleed_gate(guitar, competitor_paths={})
    assert diag.attempted is False
    assert "competitor" in diag.reason


def test_bleed_gate_default_off_in_config():
    assert IsolateConfig().bleed_gate is False
    assert IsolateConfig().adaptive_fold_gain is False


def test_fold_gain_search_fixed_gain_without_adaptive(tmp_path: Path):
    guitar = _tone_wav(tmp_path / "guitar.wav", 440.0)
    other = _tone_wav(tmp_path / "other.wav", 660.0)
    diag = apply_fold_other_gain_search(guitar, other, adaptive=False)
    assert diag.attempted is False
    assert diag.chosen_gain == 0.5
    assert diag.scores is None


def test_fold_gain_search_adaptive_picks_candidate(tmp_path: Path):
    guitar = _tone_wav(tmp_path / "guitar.wav", 440.0, amp=0.3)
    other = _tone_wav(tmp_path / "other.wav", 660.0, amp=0.3)
    bass = _tone_wav(tmp_path / "bass.wav", 55.0, amp=0.3)
    diag = apply_fold_other_gain_search(
        guitar, other, competitors={"bass": bass}, adaptive=True
    )
    assert diag.attempted is True
    assert diag.chosen_gain in FOLD_OTHER_GAIN_CANDIDATES
    assert diag.scores is not None
    assert not (tmp_path / "_fold_gain_search").exists()


def test_fold_other_adaptive_gain_writes_diagnostics(tmp_path: Path):
    guitar = _tone_wav(tmp_path / "guitar.wav", 440.0, amp=0.3)
    other = _tone_wav(tmp_path / "other.wav", 660.0, amp=0.3)
    bass = _tone_wav(tmp_path / "bass.wav", 55.0, amp=0.3)
    artifacts = {"guitar": guitar, "other": other, "bass": bass}
    artifacts, diag = apply_fold_other_into_guitar(
        artifacts, mode="full", adaptive_gain=True
    )
    assert diag.folded is True
    assert "other" not in artifacts
    diag_path = tmp_path / "adaptive_fold_gain_diagnostics.json"
    assert diag_path.is_file()
    payload = json.loads(diag_path.read_text(encoding="utf-8"))
    assert payload["attempted"] is True
    assert payload["chosen_gain"] in FOLD_OTHER_GAIN_CANDIDATES
    assert artifacts["adaptive_fold_gain_diagnostics"] == diag_path
    assert not (tmp_path / "_fold_gain_search").exists()


def test_blend_guitar_stems_identity_preserves_input(tmp_path: Path):
    primary = _tone_wav(tmp_path / "p.wav", 440.0, amp=0.2, seconds=0.2)
    secondary = _tone_wav(tmp_path / "s.wav", 440.0, amp=0.2, seconds=0.2)
    out = tmp_path / "blended.wav"
    diag = blend_guitar_stems(primary, secondary, out)
    assert diag.attempted is True
    assert diag.blended is True
    assert diag.mean_primary_weight == pytest.approx(0.5, abs=1e-3)
    a = sf.read(str(primary))[0]
    b = sf.read(str(out))[0]
    assert np.average(np.abs(a - b)) < 0.05


def test_blend_guitar_stems_favors_secondary_when_primary_silent(tmp_path: Path):
    primary = _tone_wav(tmp_path / "p.wav", 440.0, amp=1e-4)
    secondary = _tone_wav(tmp_path / "s.wav", 440.0, amp=0.4)
    out = tmp_path / "blended.wav"
    diag = blend_guitar_stems(primary, secondary, out)
    assert diag.blended is True
    assert diag.mean_primary_weight < 0.5
    b = sf.read(str(out))[0]
    assert np.sqrt(np.mean(np.square(b))) > 0.1


def test_blend_guitar_stems_missing_input_not_attempted(tmp_path: Path):
    primary = _tone_wav(tmp_path / "p.wav", 440.0)
    diag = blend_guitar_stems(primary, tmp_path / "missing.wav", tmp_path / "out.wav")
    assert diag.attempted is False
    assert not (tmp_path / "out.wav").exists()


def test_ensemble_config_constraints():
    assert IsolateConfig(model="htdemucs_6s", guitar_ensemble=True).guitar_ensemble is True
    assert (
        IsolateConfig(model="htdemucs_6s", two_pass=True, guitar_ensemble=True).guitar_ensemble
        is False
    )
    assert (
        IsolateConfig(model="bs_roformer_sw", guitar_ensemble=True).guitar_ensemble is False
    )
    assert IsolateConfig().guitar_ensemble is False


def test_isolate_timeout_multiplier_counts_ensemble_pass():
    base = isolate_timeout_multiplier(model="htdemucs_6s")
    with_ensemble = isolate_timeout_multiplier(model="htdemucs_6s", guitar_ensemble=True)
    assert with_ensemble == base + 1