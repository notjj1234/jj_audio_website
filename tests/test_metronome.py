"""Beat-tracked metronome click stem."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.metronome import (
    METRONOME_STEM_ID,
    MetronomeRenderOptions,
    apply_click_rate,
    attach_metronome_artifact,
    build_click_times,
    coerce_metronome_render_options,
    detect_beats_per_measure,
    gate_unreliable_intro_beats,
    generate_metronome_stem,
    integrate_tempo_curve,
    load_metronome_diagnostics,
    metronome_grid_times,
    octave_snap_bpm,
    pick_metronome_source,
    rebake_metronome_artifact,
    refine_tempo_phase,
    render_metronome_wav,
    collapse_brief_octave_runs,
    stabilize_tempo_curve,
    steady_click_times,
    write_metronome_diagnostics,
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


def test_build_click_times_fills_internal_gap():
    """A drum-less middle section must still get clicks on the beat grid."""
    period = 0.5
    detected = np.concatenate(
        [
            np.arange(0.0, 4.0 + 1e-9, period),
            np.arange(10.0, 14.0 + 1e-9, period),
        ]
    )
    times = build_click_times(detected, duration_sec=14.5, bpm=120.0)
    for expected in (4.5, 5.0, 6.0, 7.5, 9.0, 9.5):
        assert any(abs(float(t) - expected) < 1e-6 for t in times)
    assert float(np.max(np.diff(times))) < 1.5 * period
    # Detected beats stay exactly where the performance put them.
    for t in detected:
        assert any(abs(float(x) - float(t)) < 1e-9 for x in times)


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


def test_pick_metronome_source_prefers_full_mix_over_drums(tmp_path: Path):
    """Drums go quiet in verses; the mix keeps rhythm in every section."""
    drums = tmp_path / "drums.wav"
    _write_pulse_train(drums)
    mix = tmp_path / "song.wav"
    mix.write_bytes(b"x")
    assert pick_metronome_source({"drums": drums}, fallback=mix) == (mix, "source")
    assert pick_metronome_source({"drums": drums}) == (drums, "drums")


def test_gate_unreliable_intro_beats_drops_quiet_irregular_onsets():
    sr = 22050
    duration = 6.0
    period = 0.5
    n = int(sr * duration)
    mono = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(1)
    noise_n = int(2.0 * sr)
    mono[:noise_n] = rng.normal(0, 0.05, noise_n).astype(np.float32)
    click = int(0.02 * sr)
    body = np.arange(2.0, duration, period, dtype=np.float64)
    for t in body:
        i = int(round(float(t) * sr))
        mono[i : i + click] = 0.9
    noise_times = np.asarray([0.2, 0.51, 0.93, 1.4], dtype=np.float64)
    for t in noise_times:
        i = int(round(float(t) * sr))
        mono[i : i + int(0.01 * sr)] = 0.12
    detected = np.concatenate([noise_times, body])
    gated, body_start = gate_unreliable_intro_beats(detected, mono, sr, period)
    assert body_start == pytest.approx(2.0, abs=0.05)
    assert not any(float(t) < 1.9 for t in gated)
    assert any(abs(float(t) - 2.0) < 1e-9 for t in gated)


def test_gate_keeps_loud_pulse_train_from_start():
    sr = 22050
    period = 0.5
    duration = 4.0
    n = int(sr * duration)
    mono = np.zeros(n, dtype=np.float32)
    click = int(0.02 * sr)
    detected = np.arange(0.0, duration, period, dtype=np.float64)
    for t in detected:
        i = int(round(float(t) * sr))
        mono[i : i + click] = 0.9
    gated, body_start = gate_unreliable_intro_beats(detected, mono, sr, period)
    assert body_start == pytest.approx(0.0, abs=0.01)
    assert gated.size == detected.size


def _accented_beats(
    accent_every: int,
    *,
    beats: int = 24,
    period: float = 0.5,
    sr: int = 22050,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Beat times plus mono audio where every ``accent_every``-th beat is louder."""
    times = np.arange(beats, dtype=np.float64) * period
    mono = np.zeros(int(sr * (beats + 1) * period), dtype=np.float32)
    click = int(0.02 * sr)
    for i, t in enumerate(times):
        start = int(round(float(t) * sr))
        mono[start : start + click] = 0.9 if i % accent_every == 0 else 0.35
    return times, mono, sr


def test_detect_beats_per_measure_reads_accent_pattern():
    three, mono3, sr = _accented_beats(3)
    assert detect_beats_per_measure(three, mono3, sr, 120.0) == 3

    four, mono4, _ = _accented_beats(4)
    assert detect_beats_per_measure(four, mono4, sr, 120.0) == 4

    # No accents at all → keep the 4/4 default instead of guessing.
    flat, mono_flat, _ = _accented_beats(1)
    assert detect_beats_per_measure(flat, mono_flat, sr, 120.0) == 4

    # Too few beats to see a measure → default.
    short = np.arange(4, dtype=np.float64) * 0.5
    assert detect_beats_per_measure(short, mono3, sr, 120.0) == 4


def test_generate_metronome_detects_three_four_and_honors_override(tmp_path: Path):
    sr = 22050
    period = 0.5
    beats = 36
    duration = (beats + 1) * period
    times = np.arange(beats, dtype=np.float64) * period
    y = np.zeros(int(sr * duration), dtype=np.float32)
    click = int(0.02 * sr)
    for i, t in enumerate(times):
        start = int(round(float(t) * sr))
        y[start : start + click] = 0.9 if i % 3 == 0 else 0.35
    src = tmp_path / "waltz.wav"
    sf.write(str(src), np.column_stack([y, y]), sr, subtype="PCM_16")

    auto = generate_metronome_stem(src, tmp_path / "auto.wav")
    assert auto is not None
    assert auto.beats_per_measure == 3

    forced = generate_metronome_stem(src, tmp_path / "forced.wav", beats_per_measure=2)
    assert forced is not None
    assert forced.beats_per_measure == 2


def test_apply_click_rate_identity_and_half_and_double():
    times = np.arange(0.0, 4.0, 0.5, dtype=np.float64)
    one = apply_click_rate(times, rate=1.0, ref_sec=0.0)
    np.testing.assert_allclose(one, times)
    half = apply_click_rate(times, rate=0.5, ref_sec=0.0)
    np.testing.assert_allclose(half, np.array([0.0, 1.0, 2.0, 3.0]))
    double = apply_click_rate(times, rate=2.0, ref_sec=0.0)
    assert any(abs(float(t) - 0.25) < 1e-9 for t in double)
    assert any(abs(float(t) - 0.5) < 1e-9 for t in double)
    gappy = np.asarray([0.0, 0.5, 1.0, 5.0, 5.5], dtype=np.float64)
    doubled = apply_click_rate(gappy, rate=2.0, ref_sec=0.0)
    assert any(abs(float(t) - 0.25) < 1e-9 for t in doubled)
    assert not any(abs(float(t) - 3.0) < 0.05 for t in doubled)


def test_coerce_metronome_render_options_defaults():
    opts = coerce_metronome_render_options(accent="nope", rate="0.5x", sound="Hi-tick")
    assert opts.accent is True
    assert opts.rate == 0.5
    assert opts.sound == "hi_tick"
    bad = coerce_metronome_render_options(accent=None, rate="nope", sound="claves")
    assert bad.accent is True
    assert bad.rate == 1.0
    assert bad.sound == "classic"
    assert bad.follow == "smart"
    steady = coerce_metronome_render_options(follow="steady")
    assert steady.follow == "steady"
    assert coerce_metronome_render_options(follow="regular").follow == "smart"


def _click_peak_hz(clicks: np.ndarray, sr: int, t0: float, window: float = 0.04) -> float:
    start = int(round(t0 * sr))
    end = max(start + 8, start + int(window * sr))
    sl = np.asarray(clicks[start:end, 0], dtype=np.float64)
    if sl.size < 8:
        return 0.0
    windowed = sl * np.hanning(sl.size)
    spec = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(sl.size, 1.0 / sr)
    return float(freqs[int(np.argmax(spec))])


def test_render_accent_vs_uniform_classic(tmp_path: Path):
    sr = 22050
    n = sr * 2
    times = np.arange(0.0, 2.0, 0.5, dtype=np.float64)
    accented = tmp_path / "acc.wav"
    uniform = tmp_path / "uni.wav"
    assert render_metronome_wav(
        times,
        accented,
        sr=sr,
        n_samples=n,
        options=MetronomeRenderOptions(accent=True, rate=1.0, sound="classic"),
        ref_sec=0.0,
    )
    assert render_metronome_wav(
        times,
        uniform,
        sr=sr,
        n_samples=n,
        options=MetronomeRenderOptions(accent=False, rate=1.0, sound="classic"),
        ref_sec=0.0,
    )
    acc, _ = sf.read(str(accented), always_2d=True)
    uni, _ = sf.read(str(uniform), always_2d=True)
    down_hz = _click_peak_hz(acc, sr, 0.0)
    beat_hz = _click_peak_hz(acc, sr, 0.5)
    uni_a = _click_peak_hz(uni, sr, 0.0)
    uni_b = _click_peak_hz(uni, sr, 0.5)
    assert down_hz > beat_hz + 200
    assert abs(uni_a - uni_b) < 250


def test_sound_presets_write_audible_stereo(tmp_path: Path):
    sr = 22050
    n = sr
    times = np.asarray([0.1, 0.6], dtype=np.float64)
    for sound in ("classic", "soft", "wood", "hi_tick"):
        out = tmp_path / f"{sound}.wav"
        assert render_metronome_wav(
            times,
            out,
            sr=sr,
            n_samples=n,
            options=MetronomeRenderOptions(accent=True, rate=1.0, sound=sound),
            ref_sec=0.1,
        )
        clicks, click_sr = sf.read(str(out), always_2d=True)
        assert click_sr == sr
        assert clicks.shape == (n, 2)
        assert float(np.max(np.abs(clicks))) > 0.05


def test_generate_metronome_writes_grid_diagnostics(tmp_path: Path):
    src = tmp_path / "drums.wav"
    out = tmp_path / "metronome.wav"
    _write_pulse_train(src, bpm=120.0, duration=8.0)
    result = generate_metronome_stem(src, out, source="drums")
    assert result is not None
    assert result.render.accent is True
    assert result.render.rate == 1.0
    assert result.render.sound == "classic"
    assert len(result.click_times_1x) >= 8
    diag_path = tmp_path / "metronome_diagnostics.json"
    from audio_to_tab.metronome import write_metronome_diagnostics

    write_metronome_diagnostics(diag_path, result)
    payload = load_metronome_diagnostics(diag_path)
    assert payload is not None
    assert payload["click_times_1x"]
    assert payload["render"]["sound"] == "classic"
    assert "detected_times" in payload


def test_rebake_does_not_call_beat_track(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    src = tmp_path / "drums.wav"
    _write_pulse_train(src, bpm=120.0, duration=4.0)
    result = generate_metronome_stem(src, tmp_path / "metronome.wav", source="drums")
    assert result is not None
    from audio_to_tab.metronome import write_metronome_diagnostics

    write_metronome_diagnostics(tmp_path / "metronome_diagnostics.json", result)

    def boom(*_args, **_kwargs):
        raise AssertionError("beat_track should not run during rebake")

    monkeypatch.setattr("librosa.beat.beat_track", boom)
    rebaked = rebake_metronome_artifact(
        tmp_path,
        MetronomeRenderOptions(accent=False, rate=2.0, sound="wood"),
    )
    assert rebaked is not None
    assert rebaked.render.rate == 2.0
    assert rebaked.render.sound == "wood"
    assert rebaked.render.accent is False
    clicks, sr = sf.read(str(tmp_path / "metronome.wav"), always_2d=True)
    peaks = _peak_times(clicks, sr)
    assert any(abs(p - 0.25) < 0.08 for p in peaks)


def test_generate_metronome_talking_intro_gates_noise(tmp_path: Path):
    sr = 22050
    duration = 6.0
    n = int(sr * duration)
    y = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(2)
    noise_n = int(2.0 * sr)
    y[:noise_n] = rng.normal(0, 0.06, noise_n).astype(np.float32)
    for t in (0.18, 0.55, 1.05, 1.47):
        i = int(t * sr)
        y[i : i + int(0.01 * sr)] += 0.12
    click = int(0.02 * sr)
    t = 2.0
    while t < duration:
        start = int(round(t * sr))
        if start >= n:
            break
        y[start : min(n, start + click)] = 0.9
        t += 0.5
    src = tmp_path / "talk.wav"
    out = tmp_path / "metronome.wav"
    sf.write(str(src), np.column_stack([y, y]), sr, subtype="PCM_16")
    result = generate_metronome_stem(src, out)
    assert result is not None
    assert result.first_detected_sec == pytest.approx(2.0, abs=0.35)
    assert result.body_start_sec == pytest.approx(2.0, abs=0.35)
    assert not any(t < 1.6 for t in result.detected_times)
    assert any(abs(t - 2.0) < 0.12 for t in result.click_times_1x)
    clicks, click_sr = sf.read(str(out), always_2d=True)
    peaks = _peak_times(clicks, click_sr)
    assert peaks.size > 0
    assert any(abs(p - 2.0) < 0.12 for p in peaks)
    assert any(p < 0.12 for p in peaks)


def test_octave_snap_bpm_collapses_double_and_half():
    assert octave_snap_bpm(240.0, 120.0) == pytest.approx(120.0)
    assert octave_snap_bpm(60.0, 120.0) == pytest.approx(60.0)
    assert octave_snap_bpm(90.0, 120.0) == pytest.approx(120.0)


def test_stabilize_tempo_curve_median_then_snap():
    rng = np.random.default_rng(3)
    noisy = 120.0 + rng.uniform(-5.0, 5.0, size=400)
    curve = stabilize_tempo_curve(noisy, sr=22050, hop_length=512, global_bpm=120.0)
    assert curve.size == noisy.size
    assert float(np.max(np.abs(curve - 120.0))) < 1.0


def test_integrate_tempo_curve_constant_120():
    times = np.linspace(0.0, 4.0, 17)
    bpm = np.full(times.size, 120.0)
    out = integrate_tempo_curve(
        0.0,
        4.0,
        curve_times=times,
        curve_bpm=bpm,
        fallback_bpm=120.0,
        include_start=True,
    )
    expected = np.arange(0.0, 4.0, 0.5)
    np.testing.assert_allclose(out, expected, atol=1e-9)


def test_build_click_times_uses_local_period_in_lead_when_confident():
    detected = np.asarray([1.2, 1.8, 2.4], dtype=np.float64)
    curve_times = np.linspace(0.0, 3.0, 31)
    curve_bpm = np.full(curve_times.size, 100.0)
    conf = np.ones(curve_times.size)
    times = build_click_times(
        detected,
        duration_sec=3.0,
        bpm=120.0,
        tempo_curve=curve_bpm,
        curve_times=curve_times,
        curve_conf=conf,
    )
    assert any(abs(float(t) - 0.0) < 1e-6 for t in times)
    assert any(abs(float(t) - 0.6) < 1e-6 for t in times)
    assert not any(abs(float(t) - 0.2) < 0.04 for t in times)
    for t in detected:
        assert any(abs(float(x) - float(t)) < 1e-9 for x in times)


def test_build_click_times_without_curve_matches_today():
    detected = np.asarray([1.5, 2.0, 2.5, 3.0, 3.5], dtype=np.float64)
    times = build_click_times(detected, duration_sec=4.0, bpm=120.0)
    expected = np.arange(0.0, 4.0, 0.5)
    np.testing.assert_allclose(times, expected, atol=1e-9)
    gapped = np.concatenate(
        [
            np.arange(0.0, 4.0 + 1e-9, 0.5),
            np.arange(10.0, 14.0 + 1e-9, 0.5),
        ]
    )
    filled = build_click_times(gapped, duration_sec=14.5, bpm=120.0)
    again = build_click_times(
        gapped,
        duration_sec=14.5,
        bpm=120.0,
        tempo_curve=None,
        curve_times=None,
        curve_conf=None,
    )
    np.testing.assert_allclose(filled, again, atol=1e-9)


def test_gate_keeps_quiet_regular_intro_pulse():
    sr = 22050
    period = 0.5
    duration = 6.0
    n = int(sr * duration)
    mono = np.zeros(n, dtype=np.float32)
    click = int(0.02 * sr)
    intro = np.arange(0.15, 2.0, period, dtype=np.float64)
    drums = np.arange(2.0, duration, period, dtype=np.float64)
    for t in intro:
        i = int(round(float(t) * sr))
        mono[i : i + click] = 0.15
    for t in drums:
        i = int(round(float(t) * sr))
        mono[i : i + click] = 0.9
    detected = np.concatenate([intro, drums])
    local = np.full(detected.size, period, dtype=np.float64)
    gated, body_start = gate_unreliable_intro_beats(
        detected, mono, sr, period, local_periods=local
    )
    assert body_start == pytest.approx(2.0, abs=0.05)
    assert any(abs(float(t) - 0.15) < 1e-9 for t in gated)
    assert any(abs(float(t) - 2.0) < 1e-9 for t in gated)


def test_generate_metronome_vocal_intro_follows_local_pulse(tmp_path: Path):
    sr = 22050
    duration = 8.0
    n = int(sr * duration)
    y = np.zeros(n, dtype=np.float32)
    click = int(0.02 * sr)
    quiet = np.arange(0.15, 2.0, 0.5, dtype=np.float64)
    drums = np.arange(2.0, duration, 0.5, dtype=np.float64)
    for t in quiet:
        i = int(round(float(t) * sr))
        y[i : i + click] = 0.16
    for t in drums:
        i = int(round(float(t) * sr))
        y[i : i + click] = 0.9
    src = tmp_path / "vocal_intro.wav"
    out = tmp_path / "metronome.wav"
    sf.write(str(src), np.column_stack([y, y]), sr, subtype="PCM_16")
    result = generate_metronome_stem(src, out)
    assert result is not None
    clicks = np.asarray(result.click_times_1x, dtype=np.float64)
    intro_hits = sum(
        1 for p in quiet if any(abs(float(c) - float(p)) < 0.08 for c in clicks)
    )
    assert intro_hits >= max(2, quiet.size - 1)
    late = drums[drums >= 2.0]
    late_hits = sum(
        1 for p in late if any(abs(float(c) - float(p)) < 0.08 for c in clicks)
    )
    assert late_hits >= max(3, late.size // 2)
    assert result.body_start_sec == pytest.approx(2.0, abs=0.35)
    assert result.first_detected_sec < 1.6


def test_steady_tempo_matches_global_grid(tmp_path: Path):
    src = tmp_path / "steady.wav"
    out = tmp_path / "metronome.wav"
    _write_pulse_train(src, bpm=120.0, duration=8.0)
    result = generate_metronome_stem(src, out)
    assert result is not None
    detected = np.asarray(result.detected_times, dtype=np.float64)
    old_grid = build_click_times(
        detected, duration_sec=result.duration_sec, bpm=result.bpm
    )
    clicks = np.asarray(result.click_times_1x, dtype=np.float64)
    n = min(old_grid.size, clicks.size)
    assert n >= 8
    diffs = []
    for t in clicks:
        diffs.append(float(np.min(np.abs(old_grid - float(t)))))
    assert max(diffs) < 0.03


def test_diagnostics_bpm_curve_optional_and_rebake_preserves_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    src = tmp_path / "drums.wav"
    _write_pulse_train(src, bpm=120.0, duration=4.0)
    result = generate_metronome_stem(src, tmp_path / "metronome.wav", source="drums")
    assert result is not None
    assert result.bpm_curve_t
    assert result.bpm_curve_bpm
    assert "bpm_curve" not in result.slim_meta()
    diag = tmp_path / "metronome_diagnostics.json"
    write_metronome_diagnostics(diag, result)
    payload = load_metronome_diagnostics(diag)
    assert payload is not None
    assert payload["bpm_curve"]["t"]
    assert payload["bpm_curve"]["bpm"]

    def boom(*_args, **_kwargs):
        raise AssertionError("beat_track should not run during rebake")

    monkeypatch.setattr("librosa.beat.beat_track", boom)
    rebaked = rebake_metronome_artifact(
        tmp_path,
        MetronomeRenderOptions(accent=False, rate=1.0, sound="classic"),
    )
    assert rebaked is not None
    assert tuple(rebaked.bpm_curve_t) == tuple(result.bpm_curve_t)
    assert tuple(rebaked.bpm_curve_bpm) == tuple(result.bpm_curve_bpm)

    old_dir = tmp_path / "legacy"
    old_dir.mkdir()
    old_payload = dict(payload)
    old_payload.pop("bpm_curve", None)
    (old_dir / "metronome_diagnostics.json").write_text(
        json.dumps(old_payload), encoding="utf-8"
    )
    (tmp_path / "metronome.wav").replace(old_dir / "metronome.wav")
    legacy = rebake_metronome_artifact(
        old_dir,
        MetronomeRenderOptions(accent=True, rate=1.0, sound="classic"),
    )
    assert legacy is not None
    assert legacy.bpm_curve_t == ()
    assert legacy.bpm_curve_bpm == ()


def test_generate_metronome_48000_sr_pulse_train(tmp_path: Path):
    src = tmp_path / "drums48.wav"
    out = tmp_path / "metronome.wav"
    _write_pulse_train(src, bpm=120.0, duration=8.0, sr=48000)
    result = generate_metronome_stem(src, out, source="drums")
    assert result is not None
    assert result.sr == 48000
    assert result.bpm == pytest.approx(120.0, abs=8.0)
    assert result.beat_count >= 8
    clicks = np.asarray(result.click_times_1x, dtype=np.float64)
    assert any(abs(float(t) - 0.5) < 0.08 for t in clicks)
    assert any(abs(float(t) - 1.0) < 0.08 for t in clicks)
    assert any(abs(float(t) - 4.0) < 0.12 for t in clicks)


def _hop_frames(seconds: float, *, sr: int = 22050, hop: int = 512) -> int:
    return max(1, int(round(seconds / (hop / sr))))


def test_collapse_brief_octave_run_returns_to_anchor():
    sr, hop = 22050, 512
    n = _hop_frames(20.0, sr=sr, hop=hop)
    curve = np.full(n, 80.0)
    start = _hop_frames(4.0, sr=sr, hop=hop)
    end = start + _hop_frames(2.0, sr=sr, hop=hop)
    curve[start:end] = 160.0
    out = collapse_brief_octave_runs(curve, sr=sr, hop_length=hop, global_bpm=80.0)
    assert np.allclose(out, 80.0)


def test_collapse_keeps_long_octave_run():
    sr, hop = 22050, 512
    n = _hop_frames(24.0, sr=sr, hop=hop)
    curve = np.full(n, 80.0)
    start = _hop_frames(4.0, sr=sr, hop=hop)
    end = start + _hop_frames(12.0, sr=sr, hop=hop)
    curve[start:end] = 160.0
    out = collapse_brief_octave_runs(curve, sr=sr, hop_length=hop, global_bpm=80.0)
    assert np.allclose(out[start:end], 160.0)
    assert np.allclose(out[:start], 80.0)
    assert np.allclose(out[end:], 80.0)


def test_build_click_times_skips_short_double_after_guard():
    sr, hop = 22050, 512
    duration = 16.0
    bpm = 80.0
    period = 60.0 / bpm
    body = np.arange(0.0, duration, period)
    hop_sec = hop / sr
    n = int(round(duration / hop_sec)) + 1
    curve_times = np.arange(n) * hop_sec
    curve = np.full(n, bpm)
    start = _hop_frames(4.0, sr=sr, hop=hop)
    end = start + _hop_frames(2.0, sr=sr, hop=hop)
    curve[start:end] = 160.0
    guarded = collapse_brief_octave_runs(curve, sr=sr, hop_length=hop, global_bpm=bpm)
    clicks = build_click_times(
        body,
        duration_sec=duration,
        bpm=bpm,
        tempo_curve=guarded,
        curve_times=curve_times,
        curve_conf=np.ones(n),
    )
    diffs = np.diff(clicks)
    assert diffs.size >= 8
    assert float(np.min(diffs)) > 0.6


def test_build_click_times_keeps_long_double_body():
    slow = 0.75
    fast = 0.375
    body = np.unique(
        np.concatenate(
            [
                np.arange(0.0, 4.0, slow),
                np.arange(4.0, 16.0, fast),
                np.arange(16.0, 20.0, slow),
            ]
        )
    )
    clicks = build_click_times(body, duration_sec=20.0, bpm=80.0)
    mid = np.diff(clicks[(clicks >= 5.0) & (clicks <= 15.0)])
    edge = np.diff(clicks[(clicks >= 0.5) & (clicks <= 3.5)])
    assert mid.size >= 4
    assert edge.size >= 2
    assert float(np.median(mid)) < 0.45
    assert float(np.median(edge)) > 0.6


def test_steady_grid_is_one_period():
    times = steady_click_times(duration_sec=8.0, bpm=120.0, body_start_sec=0.25)
    diffs = np.diff(times)
    assert diffs.size >= 8
    assert np.allclose(diffs, 0.5)
    assert abs(float(times[0]) - 0.25) < 1e-9


def test_rebake_steady_keeps_smart_times_and_skips_beat_track(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sr = 22050
    duration = 4.0
    n = int(sr * duration)
    sf.write(tmp_path / "metronome.wav", np.zeros((n, 2), dtype=np.float32), sr)
    smart = [0.0, 0.4, 0.9, 1.5, 2.2, 2.8, 3.5]
    diag = tmp_path / "metronome_diagnostics.json"
    diag.write_text(
        json.dumps(
            {
                "bpm": 120.0,
                "sr": sr,
                "duration_sec": duration,
                "body_start_sec": 0.0,
                "click_times_1x": smart,
                "detected_times": [0.0, 0.5, 1.0, 1.5],
                "beats_per_measure": 4,
                "render": {"accent": True, "rate": 1.0, "sound": "classic"},
            }
        ),
        encoding="utf-8",
    )

    def boom(*_args, **_kwargs):
        raise AssertionError("beat_track should not run during rebake")

    monkeypatch.setattr("librosa.beat.beat_track", boom)
    result = rebake_metronome_artifact(
        tmp_path,
        MetronomeRenderOptions(follow="steady"),
    )
    assert result is not None
    assert result.render.follow == "steady"
    assert list(result.click_times_1x) == pytest.approx(smart)
    payload = load_metronome_diagnostics(diag)
    assert payload is not None
    assert payload["click_times_1x"] == pytest.approx(smart)
    assert payload["render"]["follow"] == "steady"
    clicks, click_sr = sf.read(tmp_path / "metronome.wav", always_2d=True)
    peaks = _peak_times(clicks, click_sr)
    expected = steady_click_times(duration_sec=duration, bpm=120.0, body_start_sec=0.0)
    assert peaks.size >= 4
    for t in expected:
        if t < duration - 0.05:
            assert any(abs(float(p) - float(t)) < 0.03 for p in peaks)
