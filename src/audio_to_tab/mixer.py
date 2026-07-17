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
)

STEM_LABELS = {
    "guitar1": "Guitar 1",
    "guitar2": "Guitar 2",
    "no_vocals": "No vocals",
    "no_drums": "No drums",
    "no_bass": "No bass",
    "no_other": "No other",
    "no_guitar": "No guitar",
    "no_piano": "No piano",
}


def stem_display_name(stem_id: str) -> str:
    if stem_id in STEM_LABELS:
        return STEM_LABELS[stem_id]
    return stem_id.replace("_", " ").title()


def sort_stem_names(names: list[str] | set[str]) -> list[str]:
    order = {name: i for i, name in enumerate(STEM_ORDER)}
    return sorted(names, key=lambda n: (order.get(n, 999), n))


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


def mix_stems_to_wav(
    stem_paths: dict[str, Path],
    audible: list[str],
    output_path: str | Path,
) -> Path:
    """Sum audible stems into one stereo WAV (float32 mix, int16 output)."""
    if not audible:
        raise ValueError("No audible stems selected for mix")

    mixed: np.ndarray | None = None
    sample_rate: int | None = None

    for name in audible:
        path = stem_paths.get(name)
        if path is None or not path.exists():
            continue
        data, sr = sf.read(str(path), always_2d=True)
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        elif data.shape[1] > 2:
            data = data[:, :2]

        if mixed is None:
            mixed = data.astype(np.float32)
            sample_rate = sr
        else:
            if sr != sample_rate:
                raise ValueError(f"Sample rate mismatch for stem {name!r}")
            if len(data) > len(mixed):
                pad = np.zeros((len(data) - len(mixed), 2), dtype=np.float32)
                mixed = np.vstack([mixed, pad])
            elif len(data) < len(mixed):
                pad = np.zeros((len(mixed) - len(data), 2), dtype=np.float32)
                data = np.vstack([data.astype(np.float32), pad])
            else:
                data = data.astype(np.float32)
            mixed = mixed + data

    if mixed is None or sample_rate is None:
        raise ValueError("Could not load any audible stem audio")

    peak = float(np.max(np.abs(mixed)))
    if peak > 1.0:
        mixed = mixed / peak

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), mixed, sample_rate, subtype="PCM_16")
    return out
