"""Beat-tracked metronome click stem."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.metronome import (
    METRONOME_STEM_ID,
    attach_metronome_artifact,
    build_click_times,
    generate_metronome_stem,
    metronome_grid_times,
    pick_metronome_source,
    refine_tempo_phase,
)


def _peak_times(clicks: np.ndarray, sr: int, *, threshold: float = 0.05) -> np.ndarray:
    env = np.max(np.abs(clicks), axis=1)
    peaks = np.where(env > threshold)[0]
    if peaks.size == 0:
        return np.zeros(0, dtype=np.float64)
    # Collapse neighboring samples from the same click into one peak.
    groups: list[int] = []
    prev = -10**9
    for idx in peaks:
        if idx - prev > int(0.02 * sr):
            groups.append(int(idx))
        prev = int(idx)
    return np.asarray(groups, dtype=np.float64) / float(sr)


def _write_pulse_train(
    path: Path,
    *,
    bpm: float = 120.0,
    duration: float = 8.0,
    sr: int = 22050,
    start_sec: float = 0.0,
) -> None:
    beat = 60.0 / bpm
    n = int(sr * duration)
    y = np.zeros(n, dtype=np.float32)
    click = int(0.02 * sr)
    i = 0
    while True:
        start = int(round((start_sec + i * beat) * sr))
        if start >= n:
            break
        if start >= 0:
            y[start : min(n, start + click)] = 0.9
        i += 1
    sf.write(str(path), np.column_stack([y, y]), sr, subtype="PCM_16")


def _write_pulses_at(
    path: Path,
    pulse_times: np.ndarray,
    *,
    duration: float,
    sr: int = 22050,
) -> None:
    n = int(sr * duration)
    y = np.zeros(n, dtype=np.float32)
    click = int(0.02 * sr)
    for t in pulse_times:
        start = int(round(float(t) * sr))
        if 0 <= start < n:
            y[start : min(n, start + click)] = 0.9
    sf.write(str(path), np.column_stack([y, y]), sr, subtype="PCM_16")


def test_generate_metronome_stem_from_pulse_train(tmp_path: Path):
    src = tmp_path / "drums.wav"
    out = tmp_path / "metronome.wav"
    _write_pulse_train(src, bpm=120.0, duration=8.0)
    info, sr = sf.read(str(src), always_2d=True)
    result = generate_metronome_stem(src, out, source="drums")
    assert result is not None
    assert result.path == out
    assert out.is_file()
    clicks, click_sr = sf.read(str(out), always_2d=True)
    assert click_sr == sr
    assert clicks.shape[0] == info.shape[0]
    assert clicks.shape[1] == 2
    assert float(np.max(np.abs(clicks))) > 0.1
    assert result.beat_count >= 8
    assert result.bpm == pytest.approx(120.0, abs=8.0)
    assert result.source == "drums"
    peaks = _peak_times(clicks, click_sr)
    assert peaks.size > 0
    assert peaks[0] < 0.08
    # Locked to the pulse train (120 BPM → every 0.5s), not free-running from t=0.
    assert any(abs(p - 0.5) < 0.08 for p in peaks)
    assert any(abs(p - 1.0) < 0.08 for p in peaks)
    # Mid/late clicks stay on the pulse grid (hybrid body, not a drifting rigid grid).
    assert any(abs(p - 4.0) < 0.12 for p in peaks)
    assert any(abs(p - 6.0) < 0.12 for p in peaks)


def test_metronome_grid_times_respects_phase():
    times = metronome_grid_times(duration_sec=4.0, bpm=120.0, phase_sec=0.0)
    assert times[0] == pytest.approx(0.0)
    assert times[1] == pytest.approx(0.5)
    offset = metronome_grid_times(duration_sec=4.0, bpm=120.0, phase_sec=0.25)
    assert offset[0] == pytest.approx(0.25)
    assert offset[1] == pytest.approx(0.75)


def test_refine_tempo_phase_locks_to_detected_onsets():
    detected = np.asarray([1.5, 2.0, 2.5, 3.0, 3.5], dtype=np.float64)
    bpm, phase = refine_tempo_phase(detected, 118.0)
    assert bpm == pytest.approx(120.0, abs=2.0)
    assert phase == pytest.approx(0.0, abs=0.05)
    times = metronome_grid_times(duration_sec=4.0, bpm=bpm, phase_sec=phase)
    assert times[0] == pytest.approx(0.0, abs=0.05)
    assert any(abs(t - 1.5) < 0.05 for t in times)


def test_build_click_times_fills_lead_in_and_keeps_body():
    detected = np.asarray([1.5, 2.0, 2.5, 3.0, 3.5], dtype=np.float64)
    times = build_click_times(detected, duration_sec=4.0, bpm=120.0)
    assert times[0] == pytest.approx(0.0)
    assert any(abs(t - 1.5) < 1e-9 for t in times)
    assert any(abs(t - 3.5) < 1e-9 for t in times)
    # Body is the detected times, not a re-gridded approximation.
    for t in detected:
        assert any(abs(x - t) < 1e-9 for x in times)


def test_build_click_times_no_mid_song_drift():
    """Tempo change mid-file: hybrid keeps late detected beats; rigid grid would miss."""
    early = np.arange(0.0, 10.0, 0.5)
    # After t=10, period stretches to 0.52s (≈115 BPM) — accumulates large error.
    late = []
    t = 10.0
    while t < 20.0:
        late.append(t)
        t += 0.52
    detected = np.unique(np.concatenate([early, np.asarray(late, dtype=np.float64)]))
    times = build_click_times(detected, duration_sec=20.0, bpm=120.0)
    last_detected = float(detected[-1])
    assert any(abs(x - last_detected) < 1e-9 for x in times)
    # Rigid 120 BPM grid from 0 never lands on the slowed late pulses.
    rigid = metronome_grid_times(duration_sec=20.0, bpm=120.0, phase_sec=0.0)
    assert not any(abs(r - last_detected) < 0.05 for r in rigid)


def test_generate_metronome_follows_tempo_change(tmp_path: Path):
    """End-to-end: late clicks stay near true pulses when tempo slows mid-file."""
    sr = 22050
    duration = 16.0
    pulses: list[float] = []
    t = 0.0
    while t < 8.0:
        pulses.append(t)
        t += 0.5
    while t < duration:
        pulses.append(t)
        t += 0.52
    pulse_arr = np.asarray(pulses, dtype=np.float64)
    src = tmp_path / "drift.wav"
    out = tmp_path / "metronome.wav"
    _write_pulses_at(src, pulse_arr, duration=duration, sr=sr)
    result = generate_metronome_stem(src, out)
    assert result is not None
    clicks, click_sr = sf.read(str(out), always_2d=True)
    peaks = _peak_times(clicks, click_sr)
    late_pulses = pulse_arr[pulse_arr >= 12.0]
    assert late_pulses.size >= 3
    # At least half of the late true pulses should have a nearby click.
    hits = sum(1 for p in late_pulses if any(abs(peak - p) < 0.12 for peak in peaks))
    assert hits >= max(2, late_pulses.size // 2)


def test_generate_metronome_fills_lead_in_and_stays_locked(tmp_path: Path):
    """Lead-in silence is filled, but clicks still land on the late pulse grid."""
    src = tmp_path / "late.wav"
    out = tmp_path / "metronome.wav"
    _write_pulse_train(src, bpm=120.0, duration=6.0, start_sec=1.5)
    result = generate_metronome_stem(src, out)
    assert result is not None
    clicks, click_sr = sf.read(str(out), always_2d=True)
    peaks = _peak_times(clicks, click_sr)
    assert peaks[0] < 0.05
    assert any(abs(p - 1.5) < 0.08 for p in peaks)
    assert any(abs(p - 2.0) < 0.08 for p in peaks)


def test_generate_metronome_keeps_offset_phase(tmp_path: Path):
    src = tmp_path / "offset.wav"
    out = tmp_path / "metronome.wav"
    _write_pulse_train(src, bpm=120.0, duration=6.0, start_sec=0.25)
    result = generate_metronome_stem(src, out)
    assert result is not None
    clicks, click_sr = sf.read(str(out), always_2d=True)
    peaks = _peak_times(clicks, click_sr)
    assert abs(peaks[0] - 0.25) < 0.08
    assert any(abs(p - 0.75) < 0.08 for p in peaks)


def test_generate_metronome_stem_silent_and_tiny_return_none(tmp_path: Path):
    silent = tmp_path / "silent.wav"
    sf.write(str(silent), np.zeros((22050, 2), dtype=np.float32), 22050, subtype="PCM_16")
    assert generate_metronome_stem(silent, tmp_path / "a.wav") is None

    tiny = tmp_path / "tiny.wav"
    sf.write(str(tiny), np.zeros((100, 2), dtype=np.float32), 22050, subtype="PCM_16")
    assert generate_metronome_stem(tiny, tmp_path / "b.wav") is None

    missing = tmp_path / "missing.wav"
    assert generate_metronome_stem(missing, tmp_path / "c.wav") is None


def test_attach_metronome_prefers_drums_and_writes_diagnostics(tmp_path: Path):
    drums = tmp_path / "drums.wav"
    vocals = tmp_path / "vocals.wav"
    _write_pulse_train(drums)
    sf.write(str(vocals), np.zeros((22050, 2), dtype=np.float32), 22050, subtype="PCM_16")
    artifacts = {"vocals": vocals, "drums": drums}
    result = attach_metronome_artifact(artifacts, tmp_path)
    assert result is not None
    assert artifacts[METRONOME_STEM_ID] == tmp_path / "metronome.wav"
    assert artifacts["metronome_diagnostics"].is_file()
    assert pick_metronome_source(artifacts)[0] == drums
    assert pick_metronome_source({"vocals": vocals})[1] == "vocals"


def test_pick_metronome_source_falls_back_to_original(tmp_path: Path):
    src = tmp_path / "song.wav"
    src.write_bytes(b"x")
    assert pick_metronome_source({}, fallback=src) == (src, "source")
    assert pick_metronome_source({}) is None
