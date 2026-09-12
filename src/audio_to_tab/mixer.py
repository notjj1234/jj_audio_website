"""Stem mixing and waveform helpers for isolation UI."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

# Preferred stem board order (unknown stems sort after these).
STEM_ORDER = (
    "vocals",
    "drums",
    "bass",
    "guitar",
    "lead_guitar",
    "rhythm_guitar",
    "guitar1",
    "guitar2",
    "piano",
    "other",
    "no_vocals",
    "no_drums",
    "no_bass",
    "no_other",
    "no_guitar",
    "no_piano",
    "metronome",
)

DEFAULT_MUTED_STEMS = frozenset({"metronome"})

STEM_LABELS = {
    "lead_guitar": "Lead Guitar",
    "rhythm_guitar": "Rhythm Guitar",
    "guitar1": "Guitar 1 (legacy)",
    "guitar2": "Guitar 2 (legacy)",
    "no_vocals": "Instrumental",
    "no_drums": "No drums",
    "no_bass": "No bass",
    "no_other": "No other",
    "no_guitar": "No guitar",
    "no_piano": "No piano",
    "metronome": "Metronome",
}

# Volume model for live mixer + export (documented for UI/JS parity).
DB_MIN = -25.0
DB_MAX = 25.0
DB_DEFAULT = 0.0
# Master-bus ceiling shared with the live Web Audio mixer (~−1 dBTP).
TRUE_PEAK_CEILING = 10.0 ** (-1.0 / 20.0)  # ≈ 0.89125 linear


def apply_true_peak_ceiling(
    mixed: np.ndarray,
    *,
    ceiling: float = TRUE_PEAK_CEILING,
) -> np.ndarray:
    """Scale a mix so sample peak does not exceed ``ceiling`` (true-peak proxy)."""
    if mixed.size == 0:
        return mixed
    peak = float(np.max(np.abs(mixed)))
    if peak <= ceiling or peak <= 0.0:
        return mixed
    return (mixed * (ceiling / peak)).astype(np.float32, copy=False)


# Composite separator joining a re-separate parent stem id to its child id,
# e.g. ``other::guitar`` (see docs/reseparate-stems.md).
_COMPOSITE_SEPARATOR = "::"

# Near-silence floor in dBFS for the re-separate silence filter.
SILENCE_DBFS_FLOOR = -120.0


def stem_display_name(stem_id: str) -> str:
    if _COMPOSITE_SEPARATOR in str(stem_id):
        parent, _, child = str(stem_id).partition(_COMPOSITE_SEPARATOR)
        parent_label = _single_stem_label(parent)
        child_label = _single_stem_label(child)
        return f"{child_label} (from {parent_label})"
    return _single_stem_label(stem_id)


def _single_stem_label(stem_id: str) -> str:
    if stem_id in STEM_LABELS:
        return STEM_LABELS[stem_id]
    return stem_id.replace("_", " ").title()


def stem_energy_db(path: str | Path) -> float:
    """RMS amplitude of a wav in dBFS (negative; ~0 dBFS = full scale).

    Mono-downmixes multichannel audio (mean across channels) and uses float64
    internally to avoid overflow/underflow. Near-silence returns
    ``SILENCE_DBFS_FLOOR`` (``-120.0``) so re-separate children that came out
    empty can be discarded.
    """
    data, _sr = sf.read(str(path), always_2d=True)
    if data.size == 0:
        return SILENCE_DBFS_FLOOR
    mono = data.mean(axis=1).astype(np.float64)
    energy = float(np.mean(mono * mono))
    if energy <= np.finfo(np.float32).tiny:
        return SILENCE_DBFS_FLOOR
    rms = float(np.sqrt(energy))
    return 20.0 * np.log10(rms)


def sort_stem_names(names: list[str] | set[str]) -> list[str]:
    order = {name: i for i, name in enumerate(STEM_ORDER)}
    return sorted(names, key=lambda n: (order.get(n, 999), n))


def default_muted_for(stem_id: str) -> bool:
    """True for utility stems that should start silent (metronome)."""
    return str(stem_id) in DEFAULT_MUTED_STEMS


def default_muted_map(stem_names: list[str] | set[str]) -> dict[str, bool]:
    return {name: default_muted_for(name) for name in stem_names}


def db_to_linear(db: float) -> float:
    """Convert dB to linear amplitude gain. At/under DB_MIN → silence."""
    if db <= DB_MIN:
        return 0.0
    return float(10.0 ** (db / 20.0))


def effective_linear_gains(
    stem_names: list[str],
    *,
    muted: dict[str, bool],
    soloed: dict[str, bool],
    volume_db: dict[str, float] | None = None,
    master_volume_db: float = DB_DEFAULT,
) -> dict[str, float]:
    """
    DAW-style mute/solo + volume → per-stem linear gains.

    - If any stem is soloed, only soloed stems are audible (mute ignored).
    - Otherwise muted stems are silent.
    - Per-stem volume and master volume are applied as dB → linear (multiplied).
    """
    volumes = volume_db or {}
    master_db = max(DB_MIN, min(DB_MAX, float(master_volume_db)))
    master_lin = db_to_linear(master_db)
    any_solo = any(soloed.get(n, False) for n in stem_names)
    gains: dict[str, float] = {}
    for name in stem_names:
        db = float(volumes.get(name, DB_DEFAULT))
        db = max(DB_MIN, min(DB_MAX, db))
        audible = soloed.get(name, False) if any_solo else not muted.get(name, False)
        gains[name] = (db_to_linear(db) * master_lin) if audible else 0.0
    return gains


def audible_stems(
    stem_names: list[str],
    *,
    muted: dict[str, bool],
    soloed: dict[str, bool],
) -> list[str]:
    """
    DAW-style solo/mute rules:
    - If any stem is soloed, only soloed stems are audible (mute ignored).
    - Otherwise, all non-muted stems are audible.
    """
    active_solo = [n for n in stem_names if soloed.get(n, False)]
    if active_solo:
        return active_solo
    return [n for n in stem_names if not muted.get(n, False)]


def waveform_peaks(path: str | Path, *, num_points: int = 200) -> np.ndarray:
    """Downsampled peak envelope for waveform proxy charts."""
    data, _sr = sf.read(str(path), always_2d=True)
    mono = np.abs(data).mean(axis=1)
    if len(mono) == 0:
        return np.zeros(num_points, dtype=np.float32)
    if len(mono) <= num_points:
        return mono.astype(np.float32)
    chunk = max(1, len(mono) // num_points)
    trimmed = mono[: chunk * num_points]
    peaks = trimmed.reshape(num_points, chunk).max(axis=1)
    return peaks.astype(np.float32)


def _load_stereo(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]
    return data.astype(np.float32), int(sr)


def _pad_or_trim(data: np.ndarray, length: int) -> np.ndarray:
    if len(data) == length:
        return data
    if len(data) > length:
        return data[:length]
    pad = np.zeros((length - len(data), 2), dtype=np.float32)
    return np.vstack([data, pad])


def mix_stems_to_wav(
    stem_paths: dict[str, Path],
    audible: list[str] | None = None,
    output_path: str | Path | None = None,
    *,
    gains: dict[str, float] | None = None,
) -> Path:
    """
    Sum stems into one stereo WAV (float32 mix, int16 output).

    If ``gains`` is provided, each stem is scaled by its linear gain (0 = silence).
    If ``gains`` is omitted, stems in ``audible`` are mixed at gain 1.0 (legacy).

    All-zero / empty contribution writes a silent WAV matching the longest stem
    (or 1 second at 44100 Hz if no stems can be loaded).
    """
    if output_path is None:
        raise ValueError("output_path is required")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if gains is not None:
        names = [n for n in gains if n in stem_paths and gains.get(n, 0.0) != 0.0]
        # Still need length reference from any available stem when silent
        length_names = list(stem_paths.keys())
    else:
        if not audible:
            # Legacy callers expected an error for empty audible; keep that when
            # gains is not used — except we now support silence via gains={}.
            raise ValueError("No audible stems selected for mix")
        names = list(audible)
        length_names = names
        gains = dict.fromkeys(names, 1.0)

    mixed: np.ndarray | None = None
    sample_rate: int | None = None
    max_len = 0

    # Establish duration/sample rate from any existing stem (including silent mix).
    for name in length_names:
        path = stem_paths.get(name)
        if path is None or not path.exists():
            continue
        info = sf.info(str(path))
        max_len = max(max_len, int(info.frames))
        if sample_rate is None:
            sample_rate = int(info.samplerate)

    for name in names:
        path = stem_paths.get(name)
        if path is None or not path.exists():
            continue
        gain = float(gains.get(name, 0.0))
        if gain == 0.0:
            continue
        data, sr = _load_stereo(path)
        if mixed is None:
            sample_rate = sr
            mixed = data * gain
            max_len = max(max_len, len(mixed))
        else:
            if sr != sample_rate:
                raise ValueError(f"Sample rate mismatch for stem {name!r}")
            if len(data) > len(mixed):
                mixed = _pad_or_trim(mixed, len(data))
            elif len(data) < len(mixed):
                data = _pad_or_trim(data, len(mixed))
            mixed = mixed + data * gain
            max_len = max(max_len, len(mixed))

    if sample_rate is None:
        sample_rate = 44100
    if max_len <= 0:
        max_len = sample_rate  # 1 second of silence

    if mixed is None:
        mixed = np.zeros((max_len, 2), dtype=np.float32)
    else:
        mixed = _pad_or_trim(mixed, max_len)

    mixed = apply_true_peak_ceiling(mixed)

    sf.write(str(out), mixed, sample_rate, subtype="PCM_16")
    return out
