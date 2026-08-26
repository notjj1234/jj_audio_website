"""Tests for multi-stem isolation (Demucs mocked)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.isolate import (
    BASS_BLEED_ENERGY_SHARE_FLOOR,
    BASS_BLEED_HPF_CUTOFF_HZ,
    BASS_BLEED_LOW_BAND_HZ,
    IsolateConfig,
    MIN_REGION_SEC,
    RegionError,
    SUPPORTED_MODELS,
    STEM_PRESENCE_ENERGY_SHARE_MIN,
    STEM_PRESENCE_FLOOR_DB,
    _trim_audio,
    analyze_bass_bleed,
    apply_bass_bleed_mitigation,
    detect_present_stems,
    effective_demucs_segment,
    format_region_label,
    probe_duration_sec,
    resolve_region,
    separate_stems,
)
from audio_to_tab.subprocess_util import subprocess_run_kwargs

# Pre-warm librosa's lazily-imported scipy submodules at collection time (not
# inside a test). Some environments trigger a one-off scipy.ndimage import
# chain that shells out via platform.win32_ver(); doing it here keeps that
# away from tests below that mock audio_to_tab.separate.subprocess.run.
import librosa  # noqa: E402

librosa.stft(np.zeros(2048, dtype=np.float32))


def test_supported_models():
    assert "htdemucs_6s" in SUPPORTED_MODELS
    assert "htdemucs" in SUPPORTED_MODELS
    assert "htdemucs_ft" in SUPPORTED_MODELS


def test_is_demucs_available_does_not_import_torch(monkeypatch):
    from audio_to_tab.separate import is_demucs_available
    import inspect

    src = inspect.getsource(is_demucs_available)
    assert "find_spec" in src
    assert "import demucs" not in src
    assert "import torch" not in src

    monkeypatch.setattr(
        "audio_to_tab.separate.importlib.util.find_spec",
        lambda name: object() if name == "demucs" else None,
    )
    assert is_demucs_available() is True
    monkeypatch.setattr(
        "audio_to_tab.separate.importlib.util.find_spec",
        lambda name: None,
    )
    assert is_demucs_available() is False


def test_isolate_config_defaults_to_full_song():
    assert IsolateConfig().max_duration_sec is None


def test_isolate_config_default_quality_is_fast():
    assert IsolateConfig().quality == "fast"


def test_effective_demucs_segment_clamps_htdemucs_6s_below_transformer_max():
    """htdemucs_6s rejects --segment > 7.8; CLI only accepts ints, so cap at 7."""
    assert effective_demucs_segment("htdemucs_6s", 8) == 7
    assert effective_demucs_segment("htdemucs_6s", 7) == 7
    assert effective_demucs_segment("htdemucs_6s", 20) == 7


def test_effective_demucs_segment_keeps_ram_target_for_four_stem_models():
    assert effective_demucs_segment("htdemucs", 8) == 8
    assert effective_demucs_segment("htdemucs_ft", 8) == 8
    assert effective_demucs_segment("htdemucs", 12) == 10


def test_effective_demucs_segment_omits_flag_when_disabled():
    assert effective_demucs_segment("htdemucs_6s", None) is None
    assert effective_demucs_segment("htdemucs_6s", 0) is None
    assert effective_demucs_segment("htdemucs_6s", -1) is None


def test_separate_stems_requires_demucs(tmp_path: Path):
    audio = tmp_path / "in.wav"
    audio.write_bytes(b"RIFF")
    with patch("audio_to_tab.isolate.is_demucs_available", return_value=False):
        with pytest.raises(RuntimeError, match="Demucs"):
            separate_stems(audio, tmp_path / "out")


def test_separate_stems_rejects_unknown_model(tmp_path: Path):
    audio = tmp_path / "in.wav"
    audio.write_bytes(b"RIFF")
    with patch("audio_to_tab.isolate.is_demucs_available", return_value=True):
        with pytest.raises(ValueError, match="Unsupported model"):
            separate_stems(audio, tmp_path / "out", IsolateConfig(model="not_a_model"))


def test_separate_stems_rejects_cuda_when_unavailable(tmp_path: Path):
    audio = tmp_path / "in.wav"
    audio.write_bytes(b"RIFF")
    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.hardware.probe_torch", return_value=(False, False)),
    ):
        with pytest.raises(RuntimeError, match="NVIDIA CUDA"):
            separate_stems(
                audio,
                tmp_path / "out",
                IsolateConfig(model="htdemucs", device="cuda"),
            )


def test_separate_stems_collects_wavs(tmp_path: Path):
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"
    seen_cmd: list[list[str]] = []

    def fake_normalize(src, dest=None):
        dest = Path(dest) if dest else tmp_path / "norm.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"norm")
        return dest

    def fake_run(cmd, capture_output=True, text=True, **_kwargs):
        # Demucs output layout: -o <dir> → <dir>/<model>/<track>/*.wav
        seen_cmd.append(list(cmd))
        assert "-m" in cmd and "demucs" in cmd
        assert "-n" in cmd and "htdemucs_6s" in cmd
        out_flag = cmd.index("-o")
        demucs_out = Path(cmd[out_flag + 1])
        track_dir = demucs_out / "htdemucs_6s" / "normalized"
        track_dir.mkdir(parents=True, exist_ok=True)
        for name in ("vocals", "drums", "bass", "other", "piano"):
            (track_dir / f"{name}.wav").write_bytes(b"stem-" + name.encode())
        # Guitar WAV must be loadable for bass-bleed / presence stages.
        sf.write(str(track_dir / "guitar.wav"), np.zeros((256, 2), dtype=np.float32), 44100)
        return MagicMock(returncode=0, stderr="", stdout="")

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=fake_normalize),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, *a, **k: p),
        patch("audio_to_tab.separate.subprocess.run", side_effect=fake_run),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(model="htdemucs_6s", quality="fast", max_duration_sec=15),
        )

    assert {"vocals", "drums", "bass", "other", "guitar", "piano"} <= set(artifacts)
    assert "guitar_split_diagnostics" not in artifacts
    assert "lead_guitar" not in artifacts
    assert "stem_presence_diagnostics" in artifacts
    for path in artifacts.values():
        assert path.exists()
        assert path.parent == out_dir
    # Default path passes --jobs 1 and --segment for RAM-safe CPU runs.
    # Demucs argparse requires an int; htdemucs_6s max training segment is 7.8
    # so we must pass 7, not 8.
    assert "--jobs" in seen_cmd[0] and "1" in seen_cmd[0]
    assert "--segment" in seen_cmd[0]
    seg_idx = seen_cmd[0].index("--segment")
    assert seen_cmd[0][seg_idx + 1] == "7"


def test_separate_stems_passes_two_stems_flag(tmp_path: Path):
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    seen: list[list[str]] = []

    def fake_normalize(src, dest=None):
        dest = Path(dest) if dest else tmp_path / "norm.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"norm")
        return dest

    def fake_run(cmd, capture_output=True, text=True, **_kwargs):
        seen.append(cmd)
        out_flag = cmd.index("-o")
        demucs_out = Path(cmd[out_flag + 1])
        track_dir = demucs_out / "htdemucs" / "normalized"
        track_dir.mkdir(parents=True, exist_ok=True)
        (track_dir / "vocals.wav").write_bytes(b"v")
        (track_dir / "no_vocals.wav").write_bytes(b"nv")
        return MagicMock(returncode=0, stderr="", stdout="")

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=fake_normalize),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, *a, **k: p),
        patch("audio_to_tab.separate.subprocess.run", side_effect=fake_run),
    ):
        artifacts = separate_stems(
            audio,
            tmp_path / "out",
            IsolateConfig(model="htdemucs", two_stems="vocals", max_duration_sec=None),
        )

    assert "--two-stems" in seen[0]
    assert "vocals" in seen[0]
    assert set(artifacts) == {"vocals", "no_vocals", "stem_presence_diagnostics"}


def _fake_normalize_factory(tmp_path: Path):
    def fake_normalize(src, dest=None):
        dest = Path(dest) if dest else tmp_path / "norm.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"norm")
        return dest

    return fake_normalize


def _fake_demucs_with_guitar(stereo_left, stereo_right, sr: int = 44100):
    def fake_run(cmd, capture_output=True, text=True, **_kwargs):
        out_flag = cmd.index("-o")
        demucs_out = Path(cmd[out_flag + 1])
        track_dir = demucs_out / "htdemucs_6s" / "normalized"
        track_dir.mkdir(parents=True, exist_ok=True)
        for name in ("vocals", "drums", "bass", "other", "piano"):
            (track_dir / f"{name}.wav").write_bytes(b"stem-" + name.encode())
        stereo = np.column_stack([stereo_left, stereo_right])
        sf.write(str(track_dir / "guitar.wav"), stereo.astype(np.float32), sr)
        return MagicMock(returncode=0, stderr="", stdout="")

    return fake_run


def test_separate_stems_lead_rhythm_when_confident(tmp_path: Path):
    """Lead/Rhythm runs only when lead_rhythm=True (CLI/eval opt-in)."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"
    sr = 44100
    n = sr * 2
    t = np.linspace(0, 2, n, endpoint=False)
    left = np.sin(2 * np.pi * 900 * t)
    right = 0.7 * np.sin(2 * np.pi * 180 * t)

    from audio_to_tab.lead_rhythm import split_lead_rhythm_guitar as real_split

    def fake_split(guitar, out, **_kw):
        return real_split(guitar, out, use_basic_pitch=False, **_kw)

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=_fake_normalize_factory(tmp_path)),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, *a, **k: p),
        patch("audio_to_tab.separate.subprocess.run", side_effect=_fake_demucs_with_guitar(left, right)),
        patch("audio_to_tab.lead_rhythm.split_lead_rhythm_guitar", side_effect=fake_split),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(model="htdemucs_6s", max_duration_sec=15, lead_rhythm=True),
        )

    assert "guitar" in artifacts
    assert "lead_guitar" in artifacts
    assert "rhythm_guitar" in artifacts
    assert "guitar_split_diagnostics" in artifacts
    assert artifacts["lead_guitar"].read_bytes() != artifacts["rhythm_guitar"].read_bytes()

    assert "stem_presence_diagnostics" in artifacts
    presence = json.loads(artifacts["stem_presence_diagnostics"].read_text(encoding="utf-8"))
    # The combined guitar stem is superseded by its own lead/rhythm split.
    assert presence["guitar"]["present"] is False
    assert "superseded" in presence["guitar"]["reason"]
    assert presence["lead_guitar"]["present"] is True
    assert presence["rhythm_guitar"]["present"] is True


def test_separate_stems_default_skips_lead_rhythm(tmp_path: Path):
    """Default isolate path never calls Lead/Rhythm post-process."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"
    sr = 44100
    n = sr * 2
    t = np.linspace(0, 2, n, endpoint=False)
    left = np.sin(2 * np.pi * 900 * t)
    right = 0.7 * np.sin(2 * np.pi * 180 * t)
    called = {"n": 0}

    def fake_split(*_a, **_kw):
        called["n"] += 1
        return {}, None

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=_fake_normalize_factory(tmp_path)),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, *a, **k: p),
        patch("audio_to_tab.separate.subprocess.run", side_effect=_fake_demucs_with_guitar(left, right)),
        patch("audio_to_tab.lead_rhythm.split_lead_rhythm_guitar", side_effect=fake_split),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(model="htdemucs_6s", max_duration_sec=15),
        )

    assert called["n"] == 0
    assert "guitar" in artifacts
    assert "lead_guitar" not in artifacts
    assert "guitar_split_diagnostics" not in artifacts


def test_separate_stems_lead_rhythm_skips_mono_by_default(tmp_path: Path):
    """Mono / low-confidence guitar does not emit Lead + Rhythm by default."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"
    sr = 44100
    n = sr * 2
    t = np.linspace(0, 2, n, endpoint=False)
    mono = np.sin(2 * np.pi * 440 * t)

    from audio_to_tab.lead_rhythm import split_lead_rhythm_guitar as real_split

    def fake_split(guitar, out, **_kw):
        return real_split(guitar, out, use_basic_pitch=False, **_kw)

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=_fake_normalize_factory(tmp_path)),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, *a, **k: p),
        patch("audio_to_tab.separate.subprocess.run", side_effect=_fake_demucs_with_guitar(mono, mono)),
        patch("audio_to_tab.lead_rhythm.split_lead_rhythm_guitar", side_effect=fake_split),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(model="htdemucs_6s", max_duration_sec=15, lead_rhythm=True),
        )

    assert "guitar" in artifacts
    assert "lead_guitar" not in artifacts
    assert "rhythm_guitar" not in artifacts
    assert "guitar_split_diagnostics" in artifacts
    diag = json.loads(artifacts["guitar_split_diagnostics"].read_text(encoding="utf-8"))
    assert diag["outcome"] == "ambiguous"
    presence = json.loads(artifacts["stem_presence_diagnostics"].read_text(encoding="utf-8"))
    assert presence["guitar"]["present"] is True
    assert "lead_guitar" not in presence or not presence.get("lead_guitar", {}).get("present", False)


def test_separate_stems_lead_rhythm_best_effort_emits_on_mono(tmp_path: Path):
    """best_effort mode still emits Lead + Rhythm on mono guitar."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"
    sr = 44100
    n = sr * 2
    t = np.linspace(0, 2, n, endpoint=False)
    mono = np.sin(2 * np.pi * 440 * t)

    from audio_to_tab.lead_rhythm import split_lead_rhythm_guitar as real_split

    def fake_split(guitar, out, **_kw):
        return real_split(guitar, out, use_basic_pitch=False, **_kw)

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=_fake_normalize_factory(tmp_path)),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, *a, **k: p),
        patch("audio_to_tab.separate.subprocess.run", side_effect=_fake_demucs_with_guitar(mono, mono)),
        patch("audio_to_tab.lead_rhythm.split_lead_rhythm_guitar", side_effect=fake_split),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(
                model="htdemucs_6s",
                max_duration_sec=15,
                lead_rhythm=True,
                lead_rhythm_mode="best_effort",
            ),
        )

    assert "guitar" in artifacts
    assert "lead_guitar" in artifacts
    assert "rhythm_guitar" in artifacts
    diag = json.loads(artifacts["guitar_split_diagnostics"].read_text(encoding="utf-8"))
    assert diag["outcome"] == "lead_rhythm"
    presence = json.loads(artifacts["stem_presence_diagnostics"].read_text(encoding="utf-8"))
    assert presence["guitar"]["present"] is False
    assert presence["lead_guitar"]["present"] is True
    assert presence["rhythm_guitar"]["present"] is True


def test_isolate_config_dual_guitar_aliases_lead_rhythm():
    cfg = IsolateConfig(dual_guitar=True)
    assert cfg.lead_rhythm is True
    assert cfg.lead_rhythm_mode == "best_effort"


def test_detect_present_stems_flags_loud_and_silent(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    loud = (0.8 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    near_silent = np.zeros_like(loud)

    loud_path = tmp_path / "loud.wav"
    silent_path = tmp_path / "silent.wav"
    sf.write(str(loud_path), loud, sr, subtype="PCM_16")
    sf.write(str(silent_path), near_silent, sr, subtype="PCM_16")

    result = detect_present_stems({"loud": loud_path, "silent": silent_path})

    assert result["loud"].present is True
    assert result["silent"].present is False
    assert 0.0 <= result["loud"].confidence <= 1.0
    assert 0.0 <= result["silent"].confidence <= 1.0
    assert result["loud"].mean_dbfs >= STEM_PRESENCE_FLOOR_DB
    assert result["silent"].reason and result["loud"].reason


def test_detect_present_stems_energy_share_can_flag_quiet_but_real_stem(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    # Loud enough in isolation to pass the floor, and its share of the total
    # RMS across the call also clears STEM_PRESENCE_ENERGY_SHARE_MIN.
    a = (0.6 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    b = (0.6 * np.sin(2 * np.pi * 660 * t)).astype(np.float32)

    a_path = tmp_path / "a.wav"
    b_path = tmp_path / "b.wav"
    sf.write(str(a_path), a, sr, subtype="PCM_16")
    sf.write(str(b_path), b, sr, subtype="PCM_16")

    result = detect_present_stems({"a": a_path, "b": b_path})

    assert result["a"].present is True
    assert result["b"].present is True
    assert result["a"].energy_share >= STEM_PRESENCE_ENERGY_SHARE_MIN
    assert result["b"].energy_share >= STEM_PRESENCE_ENERGY_SHARE_MIN


def test_detect_present_stems_handles_unreadable_file_gracefully(tmp_path: Path):
    bogus = tmp_path / "bogus.wav"
    bogus.write_bytes(b"not-a-real-wav-file")

    result = detect_present_stems({"bogus": bogus})

    assert result["bogus"].present is False
    assert result["bogus"].mean_dbfs < STEM_PRESENCE_FLOOR_DB


def _clean_guitar_chord(sr: int = 44100, dur: float = 2.0) -> np.ndarray:
    """Guitar-like chord: mostly mid content, one modest low-E fundamental."""
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    return (
        0.25 * np.sin(2 * np.pi * 82.4 * t)  # open low E — legit low content
        + 0.5 * np.sin(2 * np.pi * 196.0 * t)  # G3
        + 0.6 * np.sin(2 * np.pi * 293.7 * t)  # D4
        + 0.5 * np.sin(2 * np.pi * 370.0 * t)  # F#4
    ).astype(np.float32)


def _distorted_bass_bleed(sr: int = 44100, dur: float = 2.0) -> np.ndarray:
    """Heavy sub-guitar-range content standing in for bled-in distorted bass."""
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    return (
        0.9 * np.sin(2 * np.pi * 41.2 * t)  # bass low E1
        + 0.7 * np.sin(2 * np.pi * 55.0 * t)  # A1
        + 0.4 * np.sin(2 * np.pi * 73.4 * t)  # distortion overtone
    ).astype(np.float32)


def test_analyze_bass_bleed_flags_bass_heavy_guitar(tmp_path: Path):
    sr = 44100
    bled = _clean_guitar_chord(sr) + _distorted_bass_bleed(sr)
    path = tmp_path / "guitar.wav"
    sf.write(str(path), np.column_stack([bled, bled]), sr, subtype="PCM_16")

    diag = analyze_bass_bleed(path)

    assert diag.attempted is True
    assert diag.flagged is True
    assert diag.low_band_energy_share is not None
    assert diag.low_band_energy_share >= BASS_BLEED_ENERGY_SHARE_FLOOR
    assert diag.low_band_cutoff_hz == BASS_BLEED_LOW_BAND_HZ
    assert "bleed" in diag.reason.lower()
    assert diag.mitigation_applied is False


def test_analyze_bass_bleed_clean_guitar_not_flagged(tmp_path: Path):
    sr = 44100
    clean = _clean_guitar_chord(sr)
    path = tmp_path / "guitar.wav"
    sf.write(str(path), np.column_stack([clean, clean]), sr, subtype="PCM_16")

    diag = analyze_bass_bleed(path)

    assert diag.attempted is True
    assert diag.flagged is False
    assert diag.low_band_energy_share is not None
    assert diag.low_band_energy_share < BASS_BLEED_ENERGY_SHARE_FLOOR


def test_analyze_bass_bleed_missing_stem(tmp_path: Path):
    diag = analyze_bass_bleed(tmp_path / "missing.wav")
    assert diag.attempted is False
    assert diag.flagged is False
    assert "missing" in diag.reason.lower()


def test_apply_bass_bleed_mitigation_reduces_bleed_without_damaging_clean_signal(tmp_path: Path):
    """
    Synthetic-fixture check backing step 3's decision to implement the HPF:
    the cutoff sits below a guitar's lowest standard-tuned fundamental (~82 Hz),
    so a clean guitar signal should pass through nearly unchanged while a
    bled-heavy signal's low-band share drops measurably (partial, not full).
    """
    sr = 44100
    clean = _clean_guitar_chord(sr)
    bled = clean + _distorted_bass_bleed(sr)

    clean_path = tmp_path / "clean.wav"
    bled_path = tmp_path / "bled.wav"
    sf.write(str(clean_path), np.column_stack([clean, clean]), sr, subtype="PCM_16")
    sf.write(str(bled_path), np.column_stack([bled, bled]), sr, subtype="PCM_16")

    clean_share_before = analyze_bass_bleed(clean_path).low_band_energy_share
    bled_share_before = analyze_bass_bleed(bled_path).low_band_energy_share

    clean_out = apply_bass_bleed_mitigation(clean_path, tmp_path / "clean_mitigated.wav")
    bled_out = apply_bass_bleed_mitigation(bled_path, tmp_path / "bled_mitigated.wav")

    clean_share_after = analyze_bass_bleed(clean_out).low_band_energy_share
    bled_share_after = analyze_bass_bleed(bled_out).low_band_energy_share

    # Clean guitar content is preserved (RMS nearly unchanged, low-band share
    # barely moves) — the cutoff is below its fundamentals.
    clean_data_before, sr_a = sf.read(str(clean_path))
    clean_data_after, sr_b = sf.read(str(clean_out))
    rms_before = float(np.sqrt(np.mean(np.square(clean_data_before))))
    rms_after = float(np.sqrt(np.mean(np.square(clean_data_after))))
    assert rms_after / rms_before > 0.95
    assert abs(clean_share_after - clean_share_before) < 0.05

    # Bled signal's low-band share measurably drops — a partial reduction,
    # not full removal (bleed harmonics above the cutoff remain).
    assert bled_share_after < bled_share_before
    assert bled_share_after > 0.0  # still some low content — not a full fix


def _fake_demucs_with_guitar_mono(mono: np.ndarray, sr: int = 44100):
    def fake_run(cmd, capture_output=True, text=True, **_kwargs):
        out_flag = cmd.index("-o")
        demucs_out = Path(cmd[out_flag + 1])
        track_dir = demucs_out / "htdemucs_6s" / "normalized"
        track_dir.mkdir(parents=True, exist_ok=True)
        for name in ("vocals", "drums", "bass", "other", "piano"):
            (track_dir / f"{name}.wav").write_bytes(b"stem-" + name.encode())
        stereo = np.column_stack([mono, mono])
        sf.write(str(track_dir / "guitar.wav"), stereo.astype(np.float32), sr)
        return MagicMock(returncode=0, stderr="", stdout="")

    return fake_run


def test_separate_stems_writes_bass_bleed_diagnostics(tmp_path: Path):
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"
    sr = 44100
    bled = _clean_guitar_chord(sr) + _distorted_bass_bleed(sr)

    from audio_to_tab.lead_rhythm import split_lead_rhythm_guitar as real_split

    def fake_split(guitar, out, **_kw):
        return real_split(guitar, out, use_basic_pitch=False, **_kw)

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=_fake_normalize_factory(tmp_path)),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, *a, **k: p),
        patch("audio_to_tab.separate.subprocess.run", side_effect=_fake_demucs_with_guitar_mono(bled, sr)),
        patch("audio_to_tab.lead_rhythm.split_lead_rhythm_guitar", side_effect=fake_split),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(model="htdemucs_6s", max_duration_sec=15),
        )

    assert "bass_bleed_diagnostics" in artifacts
    diag_data = json.loads(artifacts["bass_bleed_diagnostics"].read_text(encoding="utf-8"))
    assert diag_data["attempted"] is True
    assert diag_data["flagged"] is True
    assert diag_data["mitigation_applied"] is False  # default off
    assert diag_data["reason"]


def test_separate_stems_bass_bleed_mitigation_is_opt_in(tmp_path: Path):
    """Default config: flagged but guitar audio is left untouched."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"
    sr = 44100
    bled = _clean_guitar_chord(sr) + _distorted_bass_bleed(sr)

    from audio_to_tab.lead_rhythm import split_lead_rhythm_guitar as real_split

    def fake_split(guitar, out, **_kw):
        return real_split(guitar, out, use_basic_pitch=False, **_kw)

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=_fake_normalize_factory(tmp_path)),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, *a, **k: p),
        patch("audio_to_tab.separate.subprocess.run", side_effect=_fake_demucs_with_guitar_mono(bled, sr)),
        patch("audio_to_tab.lead_rhythm.split_lead_rhythm_guitar", side_effect=fake_split),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(model="htdemucs_6s", max_duration_sec=15, bass_bleed_mitigation=False),
        )

    diag_data = json.loads(artifacts["bass_bleed_diagnostics"].read_text(encoding="utf-8"))
    assert diag_data["flagged"] is True
    assert diag_data["mitigation_applied"] is False

    # Guitar audio on disk is untouched — re-measuring it matches the recorded share.
    unmitigated_share = analyze_bass_bleed(artifacts["guitar"]).low_band_energy_share
    assert unmitigated_share == pytest.approx(diag_data["low_band_energy_share"], abs=1e-6)


def test_separate_stems_bass_bleed_mitigation_when_enabled(tmp_path: Path):
    """Opt-in mitigation: guitar stem is high-passed and diagnostics record it."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"
    sr = 44100
    clean = _clean_guitar_chord(sr)
    bled = clean + _distorted_bass_bleed(sr)

    from audio_to_tab.lead_rhythm import split_lead_rhythm_guitar as real_split

    def fake_split(guitar, out, **_kw):
        return real_split(guitar, out, use_basic_pitch=False, **_kw)

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=_fake_normalize_factory(tmp_path)),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, *a, **k: p),
        patch("audio_to_tab.separate.subprocess.run", side_effect=_fake_demucs_with_guitar_mono(bled, sr)),
        patch("audio_to_tab.lead_rhythm.split_lead_rhythm_guitar", side_effect=fake_split),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(model="htdemucs_6s", max_duration_sec=15, bass_bleed_mitigation=True),
        )

    diag_data = json.loads(artifacts["bass_bleed_diagnostics"].read_text(encoding="utf-8"))
    assert diag_data["flagged"] is True
    assert diag_data["mitigation_applied"] is True
    assert "mitigation applied" in diag_data["reason"].lower()

    mitigated_share = analyze_bass_bleed(artifacts["guitar"]).low_band_energy_share
    assert mitigated_share < diag_data["low_band_energy_share"]


def test_isolate_config_default_start_sec():
    assert IsolateConfig().start_sec == 0.0


def test_probe_duration_passes_no_window_kwargs(tmp_path: Path, monkeypatch):
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"x")

    seen: list[dict] = []

    def fake_run(cmd, **kwargs):
        seen.append(kwargs)
        return MagicMock(returncode=0, stdout="120.5\n", stderr="")

    monkeypatch.setattr("audio_to_tab.isolate.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("audio_to_tab.isolate.subprocess.run", fake_run)

    assert probe_duration_sec(wav) == 120.5
    assert seen
    expected = subprocess_run_kwargs()
    if expected:
        assert seen[0].get("creationflags") == expected["creationflags"]
    else:
        assert "creationflags" not in seen[0]


def test_trim_audio_full_file_unchanged(tmp_path: Path):
    src = tmp_path / "norm.wav"
    src.write_bytes(b"wav")
    assert _trim_audio(src, None, start_sec=0.0) == src


def test_trim_audio_builds_ss_before_input(tmp_path: Path):
    src = tmp_path / "norm.wav"
    src.write_bytes(b"wav")
    seen: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        out = Path(cmd[-1])
        out.write_bytes(b"trimmed")
        return MagicMock(returncode=0)

    with patch("audio_to_tab.isolate.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "audio_to_tab.isolate.subprocess.run", side_effect=fake_run
    ):
        out = _trim_audio(src, 30.0, start_sec=10.0)

    assert out.exists()
    cmd = seen[0]
    ss_idx = cmd.index("-ss")
    i_idx = cmd.index("-i")
    t_idx = cmd.index("-t")
    assert cmd[ss_idx + 1] == "10.0"
    assert ss_idx < i_idx < t_idx
    assert cmd[t_idx + 1] == "30.0"


def test_trim_audio_start_zero_with_length(tmp_path: Path):
    src = tmp_path / "norm.wav"
    src.write_bytes(b"wav")

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"trimmed")
        return MagicMock(returncode=0)

    with patch("audio_to_tab.isolate.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "audio_to_tab.isolate.subprocess.run", side_effect=fake_run
    ):
        out = _trim_audio(src, 90.0, start_sec=0.0)

    assert out.name.endswith("_trim.wav")


def test_resolve_region_rejects_invalid_ranges():
    with pytest.raises(RegionError, match="less than"):
        resolve_region(120.0, 60.0, 30.0)
    with pytest.raises(RegionError, match="exceeds"):
        resolve_region(60.0, 0.0, 90.0)
    with pytest.raises(RegionError, match="at least"):
        resolve_region(120.0, 0.0, 3.0)


def test_resolve_region_clamps_to_cap_without_moving_start():
    start, length, note = resolve_region(120.0, 30.0, 90.0, cap_sec=45.0)
    assert start == 30.0
    assert length == 45.0
    assert note is not None


def test_format_region_label():
    assert format_region_label(32.0, 43.0) == "0:32–1:15"


def test_guitar_ft_fallback_to_stock_demucs_on_load_failure(tmp_path: Path):
    """Missing guitar-ft weights fall back to stock htdemucs_6s without failing the job."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"
    sr = 44100
    n = sr * 2
    t = np.linspace(0, 2, n, endpoint=False)
    left = np.sin(2 * np.pi * 900 * t)
    right = 0.7 * np.sin(2 * np.pi * 180 * t)

    def fail_guitar_ft(*_a, **_k):
        raise RuntimeError("mock missing guitar-ft weights")

    from audio_to_tab.lead_rhythm import LeadRhythmDiagnostics, split_lead_rhythm_guitar as real_split

    def fake_split(guitar, out, **_kw):
        return real_split(guitar, out, use_basic_pitch=False, **_kw)

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=_fake_normalize_factory(tmp_path)),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, *a, **k: p),
        patch("audio_to_tab.isolate.run_demucs_guitar_ft_inprocess", side_effect=fail_guitar_ft),
        patch("audio_to_tab.separate.subprocess.run", side_effect=_fake_demucs_with_guitar(left, right)),
        patch("audio_to_tab.lead_rhythm.split_lead_rhythm_guitar", side_effect=fake_split),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(
                model="htdemucs_6s",
                max_duration_sec=15,
                guitar_checkpoint="htdemucs_6s_guitar_ft",
            ),
        )

    assert "guitar" in artifacts


def test_probe_duration_sec_ffmpeg_stderr_fallback(tmp_path: Path):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"fake")

    def fake_which(name: str):
        if name == "ffprobe":
            return None
        if name == "ffmpeg":
            return "/usr/bin/ffmpeg"
        return None

    with patch("audio_to_tab.isolate.shutil.which", side_effect=fake_which), patch(
        "audio_to_tab.isolate.subprocess.run",
        return_value=MagicMock(
            returncode=1,
            stderr="Duration: 00:02:05.50, start: 0.000000, bitrate: 128 kb/s\n",
        ),
    ):
        dur = probe_duration_sec(audio)
    assert dur == pytest.approx(125.5, abs=0.01)
