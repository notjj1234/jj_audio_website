"""Tests for lead/rhythm guitar post-process."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.lead_rhythm import (
    ROLE_MARGIN_MIN,
    SEPARABILITY_FLOOR,
    SPATIAL_CORR_MAX,
    SPATIAL_CORR_RELAXED_MAX,
    SPECTRAL_SEPARABILITY_FLOOR,
    LeadRhythmDiagnostics,
    LeadRhythmThresholds,
    build_midside_pair,
    build_register_pair,
    build_spatial_pair,
    build_spectral_pair,
    classify_lead_rhythm_roles,
    extract_role_features_from_notes,
    score_candidate_pair,
    split_lead_rhythm_guitar,
    RoleFeatures,
)


def _write_stereo(path: Path, left: np.ndarray, right: np.ndarray, sr: int = 44100) -> None:
    sf.write(str(path), np.column_stack([left, right]).astype(np.float32), sr, subtype="PCM_16")


def test_diagnostics_json_roundtrip(tmp_path: Path):
    diag = LeadRhythmDiagnostics(
        outcome="ambiguous",
        reason="test",
        separability_score=0.1,
        method="none",
    )
    path = diag.write_json(tmp_path / "guitar_split_diagnostics.json")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "ambiguous" in text
    assert diag.to_dict()["reason"] == "test"


def test_spatial_pair_hard_pan(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 1.5, int(sr * 1.5), endpoint=False)
    left = np.sin(2 * np.pi * 220 * t)
    right = np.sin(2 * np.pi * 880 * t)
    path = tmp_path / "guitar.wav"
    _write_stereo(path, left, right, sr)
    pair = build_spatial_pair(path)
    assert pair is not None
    assert pair.method == "spatial"
    assert pair.separability >= SEPARABILITY_FLOOR * 0.5


def test_spatial_pair_rejects_identical_channels(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    mono = np.sin(2 * np.pi * 440 * t)
    path = tmp_path / "guitar.wav"
    _write_stereo(path, mono, mono, sr)
    assert build_spatial_pair(path) is None


def _mild_pan_two_guitar_signal(
    sr: int = 44100, dur: float = 2.0, lead_hz: float = 659.25, rhythm_hz: float = 146.83
) -> tuple[np.ndarray, np.ndarray]:
    """
    Two genuinely distinct guitar-like tones (E5 "lead" / D3 "rhythm") summed with
    only slight panning (55/45), not hard-panned. Raw sample correlation for two
    independent sources panned (p, 1-p) is 2p(1-p)/(p^2+(1-p)^2), which is already
    ~0.98 here — above SPATIAL_CORR_MAX — even though the channels are genuinely
    distinct (see lead_rhythm.py module docstring "Root cause").
    """
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    lead = np.sin(2 * np.pi * lead_hz * t)
    rhythm = np.sin(2 * np.pi * rhythm_hz * t)
    left = 0.55 * lead + 0.45 * rhythm
    right = 0.45 * lead + 0.55 * rhythm
    return left, right


def test_spatial_pair_accepts_mild_pan_with_pitch_divergence(tmp_path: Path):
    """
    Old single-correlation-gate behavior would reject this (corr > SPATIAL_CORR_MAX)
    even though the channels carry clearly different predominant pitch content.
    Pitch-divergence evidence (no split required) rescues it below the relaxed
    ceiling.
    """
    sr = 44100
    left, right = _mild_pan_two_guitar_signal(sr)
    corr = float(np.corrcoef(left, right)[0, 1])
    assert SPATIAL_CORR_MAX < corr < SPATIAL_CORR_RELAXED_MAX

    path = tmp_path / "guitar.wav"
    _write_stereo(path, left, right, sr)
    pair = build_spatial_pair(path)
    assert pair is not None
    assert pair.method == "spatial"
    assert pair.correlation == pytest.approx(corr, abs=1e-4)
    assert pair.pitch_evidence is not None
    assert pair.pitch_evidence["divergence_semitones"] >= 3.0


def test_spatial_pair_still_rejects_mild_pan_same_pitch(tmp_path: Path):
    """
    Double-tracked-style content (same fundamental in both channels, just mildly
    panned) must NOT be rescued by pitch-divergence evidence — there is no real
    divergence to find, so it stays rejected (prefer ambiguous over mislabeling).
    """
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    rng = np.random.RandomState(0)
    take1 = np.sin(2 * np.pi * 220.3 * t) + 0.02 * rng.randn(len(t))
    take2 = np.sin(2 * np.pi * 219.7 * t) + 0.02 * rng.randn(len(t))
    left = 0.55 * take1 + 0.45 * take2
    right = 0.45 * take1 + 0.55 * take2
    corr = float(np.corrcoef(left, right)[0, 1])
    assert corr > SPATIAL_CORR_MAX

    path = tmp_path / "guitar.wav"
    _write_stereo(path, left, right, sr)
    assert build_spatial_pair(path) is None


def test_split_lead_rhythm_detects_mild_pan_two_guitar(tmp_path: Path):
    """
    End-to-end: a genuinely two-guitar signal that is mildly panned (not hard-panned,
    not dead-centered) now resolves to lead_rhythm via the spatial method, where the
    pre-fix single-correlation-gate logic would have found no admissible candidate
    pair at all and returned ambiguous.
    """
    sr = 44100
    left, right = _mild_pan_two_guitar_signal(sr)
    guitar = tmp_path / "guitar.wav"
    _write_stereo(guitar, left, right, sr)

    extra, diag = split_lead_rhythm_guitar(guitar, tmp_path, use_basic_pitch=False)
    assert diag.outcome == "lead_rhythm"
    assert diag.method == "spatial"
    assert "lead_guitar" in extra and "rhythm_guitar" in extra
    assert diag.features.get("pitch_evidence") is not None


def test_score_candidate_pair_similar_is_low():
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    a = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    b = (a * 0.95).astype(np.float32)
    assert score_candidate_pair(a, b, sr) < SEPARABILITY_FLOOR


def test_score_candidate_pair_distinct_is_higher():
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    a = np.sin(2 * np.pi * 200 * t).astype(np.float32)
    b = np.sin(2 * np.pi * 2000 * t).astype(np.float32)
    assert score_candidate_pair(a, b, sr) > score_candidate_pair(a, a * 0.9, sr)


def test_classify_roles_clear_margin():
    lead = RoleFeatures(78.0, 12.0, 2.0, 1.1, 95.0, 0.4)
    rhythm = RoleFeatures(52.0, 4.0, 6.0, 2.8, 70.0, 0.12)
    assignment, margin, _ = classify_lead_rhythm_roles(lead, rhythm)
    assert assignment == "a_lead"
    assert margin >= ROLE_MARGIN_MIN


def test_classify_roles_ambiguous_when_similar():
    a = RoleFeatures(60.0, 5.0, 3.0, 1.5, 80.0, 0.2)
    b = RoleFeatures(61.0, 5.0, 3.1, 1.5, 80.0, 0.2)
    assignment, margin, _ = classify_lead_rhythm_roles(a, b)
    assert assignment == "ambiguous"
    assert margin < ROLE_MARGIN_MIN


def test_extract_role_features_from_notes():
    notes = [
        SimpleNamespace(pitch=76, velocity=90, start=0.0, end=0.4),
        SimpleNamespace(pitch=79, velocity=88, start=0.5, end=0.9),
        SimpleNamespace(pitch=72, velocity=85, start=1.0, end=1.3),
    ]
    feat = extract_role_features_from_notes(notes, duration_sec=2.0)
    assert feat.pitch_median == pytest.approx(76.0)
    assert feat.note_density == pytest.approx(1.5)
    assert feat.pitch_iqr >= 0.0


def test_role_scores_use_iqr_sustain_velocity():
    wide = RoleFeatures(70.0, 16.0, 2.0, 1.2, 100.0, 0.5)
    narrow = RoleFeatures(70.0, 2.0, 2.0, 1.2, 50.0, 0.1)
    assert wide.lead_score() > narrow.lead_score()
    assert narrow.rhythm_score() > wide.rhythm_score()


def test_split_lead_rhythm_success_without_basic_pitch(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    left = np.sin(2 * np.pi * 900 * t)  # lead-ish high
    right = 0.6 * np.sin(2 * np.pi * 180 * t)  # rhythm-ish low
    guitar = tmp_path / "guitar.wav"
    _write_stereo(guitar, left, right, sr)

    extra, diag = split_lead_rhythm_guitar(guitar, tmp_path, use_basic_pitch=False)
    assert diag.outcome == "lead_rhythm"
    assert "lead_guitar" in extra and "rhythm_guitar" in extra
    assert "guitar_split_diagnostics" in extra
    assert extra["guitar_split_diagnostics"].exists()
    assert guitar.exists()


def test_split_lead_rhythm_mono_skips_by_default(tmp_path: Path):
    """Mono guitar does not emit Lead/Rhythm in confident mode."""
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    mono = np.sin(2 * np.pi * 440 * t)
    guitar = tmp_path / "guitar.wav"
    _write_stereo(guitar, mono, mono, sr)
    extra, diag = split_lead_rhythm_guitar(guitar, tmp_path, use_basic_pitch=False)
    assert diag.outcome == "ambiguous"
    assert "lead_guitar" not in extra
    assert "rhythm_guitar" not in extra
    assert diag.forced_emit or diag.low_confidence
    assert "guitar_split_diagnostics" in extra
    assert guitar.exists()


def test_split_lead_rhythm_mono_emits_best_effort(tmp_path: Path):
    """Mono guitar still gets Lead/Rhythm WAVs when best_effort is requested."""
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    mono = np.sin(2 * np.pi * 440 * t)
    guitar = tmp_path / "guitar.wav"
    _write_stereo(guitar, mono, mono, sr)
    extra, diag = split_lead_rhythm_guitar(
        guitar, tmp_path, use_basic_pitch=False, emit_mode="best_effort"
    )
    assert diag.outcome == "lead_rhythm"
    assert "lead_guitar" in extra and "rhythm_guitar" in extra
    assert diag.forced_emit or diag.low_confidence
    assert "guitar_split_diagnostics" in extra
    assert guitar.exists()


def test_split_prefers_spatial_over_spectral(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    left = np.sin(2 * np.pi * 900 * t)
    right = 0.6 * np.sin(2 * np.pi * 180 * t)
    guitar = tmp_path / "guitar.wav"
    _write_stereo(guitar, left, right, sr)
    _, diag = split_lead_rhythm_guitar(guitar, tmp_path, use_basic_pitch=False)
    assert diag.outcome == "lead_rhythm"
    assert diag.method == "spatial"


def test_spectral_emit_quarantined_falls_back_to_musical_pair(tmp_path: Path):
    """HPSS-only path must not be the emit source; fallback still emits Lead/Rhythm."""
    sr = 44100
    t = np.linspace(0, 1.5, int(sr * 1.5), endpoint=False)
    mono = np.sin(2 * np.pi * 440 * t) + 0.5 * np.random.RandomState(0).randn(len(t))
    guitar = tmp_path / "guitar.wav"
    _write_stereo(guitar, mono.astype(np.float32), mono.astype(np.float32), sr)
    assert build_spatial_pair(guitar) is None

    thr = LeadRhythmThresholds(
        register_separability_floor=0.99,
        allow_spectral_emit=False,
    )
    extra, diag = split_lead_rhythm_guitar(
        guitar, tmp_path, use_basic_pitch=False, thresholds=thr, emit_mode="best_effort"
    )
    assert "lead_guitar" in extra and "rhythm_guitar" in extra
    assert diag.outcome == "lead_rhythm"
    assert diag.method != "spectral" or thr.allow_spectral_emit
    assert diag.method in ("register", "midside", "spatial")


def test_spectral_long_tail_silence_pad(tmp_path: Path):
    """Spectral pad must not duplicate mono into both streams."""
    sr = 8000  # lower rate → shorter arrays for HPSS
    thr = LeadRhythmThresholds(analyze_window_sec=1.0)
    n = int(sr * 1.5)
    t = np.linspace(0, 1.5, n, endpoint=False)
    mono = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    # Strong energy only in the post-window tail.
    mono[:sr] *= 0.05
    mono[sr:] = 0.6 * np.sin(2 * np.pi * 880 * t[sr:])
    guitar = tmp_path / "guitar.wav"
    _write_stereo(guitar, mono, mono, sr)
    pair = build_spectral_pair(guitar, thresholds=thr)
    assert pair is not None
    assert len(pair.a) == n and len(pair.b) == n
    tail_a = pair.a[sr:]
    tail_b = pair.b[sr:]
    assert float(np.max(np.abs(tail_a))) < 1e-3
    assert float(np.max(np.abs(tail_b))) < 1e-3
    # Legacy bug would have correlated identical mono tails:
    assert not np.allclose(tail_a, mono[sr:] * 0.65, atol=1e-3)


def test_register_pair_builds_for_broadband(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    mono = (np.sin(2 * np.pi * 200 * t) + 0.5 * np.sin(2 * np.pi * 1200 * t)).astype(
        np.float32
    )
    path = tmp_path / "guitar.wav"
    _write_stereo(path, mono, mono, sr)
    pair = build_register_pair(path)
    assert pair is not None
    assert pair.method == "register"
    assert pair.separability >= 0.0


def test_resolve_lead_rhythm_mode_defaults_and_alias():
    from audio_to_tab.lead_rhythm import resolve_lead_rhythm_mode

    assert resolve_lead_rhythm_mode(None) == "confident"
    assert resolve_lead_rhythm_mode("confident") == "confident"
    assert resolve_lead_rhythm_mode("best_effort") == "best_effort"
    assert resolve_lead_rhythm_mode(None, lead_rhythm=True) == "best_effort"


def test_thresholds_from_env(monkeypatch):
    monkeypatch.setenv("ATT_LR_SEPARABILITY_FLOOR", "0.33")
    monkeypatch.setenv("ATT_LR_ALLOW_SPECTRAL_EMIT", "true")
    thr = LeadRhythmThresholds.from_env()
    assert thr.separability_floor == pytest.approx(0.33)
    assert thr.allow_spectral_emit is True


def test_classify_roles_respects_custom_margin_min():
    lead = RoleFeatures(70.0, 4.0, 2.5, 1.3, 90.0, 0.3)
    rhythm = RoleFeatures(55.0, 10.0, 5.0, 2.2, 70.0, 0.15)
    assignment, margin, detail = classify_lead_rhythm_roles(
        lead, rhythm, margin_min=0.99
    )
    assert assignment == "ambiguous"
    assert detail["margin_min"] == 0.99
    assert margin < 0.99


def test_spectral_pair_runs(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 1.5, int(sr * 1.5), endpoint=False)
    left = np.sin(2 * np.pi * 440 * t) + 0.3 * np.random.RandomState(0).randn(len(t))
    right = left.copy()
    path = tmp_path / "guitar.wav"
    _write_stereo(path, left, right, sr)
    pair = build_spectral_pair(path)
    assert pair is None or pair.method == "spectral"


def test_eval_scorer_aggregate_metrics():
    from eval.lead_rhythm.score_lead_rhythm import ClipResult, aggregate

    rows = [
        ClipResult("a", "hard_pan", 2, "left", "lead_rhythm", "spatial", True, True, 0.3, 0.5, "ok", 0.1),
        ClipResult("b", "mono_single", 1, None, "ambiguous", "none", False, None, None, None, "no", 0.1),
        ClipResult("c", "centered_overlap", 2, None, "ambiguous", "register", False, None, 0.1, 0.2, "low", 0.1),
        ClipResult("d", "hard_pan", 2, "left", "lead_rhythm", "spatial", True, False, 0.2, 0.4, "ok", 0.1),
    ]
    s = aggregate(rows)
    assert s["n"] == 4
    assert s["split_precision"] == pytest.approx(1.0)  # both emits are gt_parts=2
    assert s["split_recall"] == pytest.approx(2 / 3)
    assert s["ambiguous_rate_on_gt_le1"] == pytest.approx(1.0)
    assert s["label_correctness"] == pytest.approx(0.5)


def test_midside_pair_centered_lead_wide_rhythm(tmp_path: Path):
    """Centered lead (Mid) + wide-panned rhythm (Side) should admit midside."""
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    lead = np.sin(2 * np.pi * 880 * t)  # center
    rhythm = np.sin(2 * np.pi * 220 * t)  # wide L/R opposite
    left = 0.7 * lead + 0.55 * rhythm
    right = 0.7 * lead - 0.55 * rhythm
    path = tmp_path / "guitar.wav"
    _write_stereo(path, left, right, sr)
    pair = build_midside_pair(path)
    assert pair is not None
    assert pair.method == "midside"
    assert pair.balance_ratio is not None and pair.balance_ratio >= 0.04


def test_midside_pair_rejects_identical_mono(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    mono = np.sin(2 * np.pi * 440 * t)
    path = tmp_path / "guitar.wav"
    _write_stereo(path, mono, mono, sr)
    assert build_midside_pair(path) is None


def test_split_midside_centered_lead_wide_rhythm(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    lead = np.sin(2 * np.pi * 880 * t)
    rhythm = 0.6 * np.sin(2 * np.pi * 180 * t)
    left = 0.7 * lead + rhythm
    right = 0.7 * lead - rhythm
    guitar = tmp_path / "guitar.wav"
    _write_stereo(guitar, left, right, sr)
    # Sine proxy admits spatially but role margin is low → confident skips emit.
    extra_conf, diag_conf = split_lead_rhythm_guitar(
        guitar, tmp_path / "conf", use_basic_pitch=False, emit_mode="confident"
    )
    assert diag_conf.outcome == "ambiguous"
    assert "lead_guitar" not in extra_conf

    extra, diag = split_lead_rhythm_guitar(
        guitar, tmp_path / "be", use_basic_pitch=False, emit_mode="best_effort"
    )
    assert diag.outcome == "lead_rhythm"
    assert "lead_guitar" in extra and "rhythm_guitar" in extra
    assert diag.method in ("midside", "spatial", "register")


def test_default_isolate_selected_stems_combined_guitar_only():
    from ui.isolate_state import custom_selected_stems

    selected = custom_selected_stems(
        ["vocals", "guitar", "lead_guitar", "rhythm_guitar"],
        ("guitar",),
    )
    assert selected["guitar"] is True
    assert selected["lead_guitar"] is False
    assert selected["rhythm_guitar"] is False
    assert selected["vocals"] is False


def test_si_sdr_prefers_matching_assignment(tmp_path: Path):
    """Eval scorer SI-SDR helpers: identical signals score high; swap still finds best pair."""
    from eval.lead_rhythm.score_lead_rhythm import _best_si_sdr_pair, _si_sdr

    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    lead = np.sin(2 * np.pi * 660 * t).astype(np.float32)
    rhythm = np.sin(2 * np.pi * 150 * t).astype(np.float32)
    assert _si_sdr(lead, lead) > 40.0
    # Direct assignment
    dl, dr = _best_si_sdr_pair(lead, rhythm, lead, rhythm)
    assert dl > 40.0 and dr > 40.0
    # Swapped estimates still recover via best-of-two
    sl, sr_ = _best_si_sdr_pair(rhythm, lead, lead, rhythm)
    assert sl > 40.0 and sr_ > 40.0


def test_make_synthetic_clips_writes_mild_pan(tmp_path: Path):
    from eval.lead_rhythm.make_synthetic_clips import mild_pan

    entry = mild_pan(tmp_path)
    assert entry["mix_type"] == "mild_pan"
    guitar = tmp_path / "mild_pan_example" / "guitar.wav"
    assert guitar.exists()
    assert (tmp_path / "mild_pan_example" / "gt_lead.wav").exists()
    assert (tmp_path / "mild_pan_example" / "gt_rhythm.wav").exists()


def test_isolate_default_stage1_model_is_htdemucs_6s():
    from audio_to_tab.isolate import IsolateConfig, SUPPORTED_MODELS
    from ui.isolate_state import DEFAULT_TRACK_OPTIONS, resolve_track_selection

    assert IsolateConfig().model == "htdemucs_6s"
    assert "htdemucs_6s" in SUPPORTED_MODELS
    default = resolve_track_selection(DEFAULT_TRACK_OPTIONS)
    assert default["model"] == "htdemucs_6s"
    assert default["emit_stems"] == ("vocals", "guitar")
    assert "piano" not in default["emit_stems"]
