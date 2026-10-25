"""Run Demucs with a soundfile-backed WAV writer.

Why this exists
---------------
``torchaudio>=2.9`` delegates ``torchaudio.save`` to ``torchcodec``.  TorchCodec
ships prebuilt libraries for FFmpeg 4-8; with FFmpeg 9 installed (Homebrew in
2026) saving a stem raises ``Could not load libtorchcodec`` *after* the model has
already finished separating.  Demucs only writes WAV files, so we replace its
writer with ``soundfile`` (already a project dependency via librosa) instead of
pinning FFmpeg or adding another dependency.

Used by ``audio_to_tab.separate`` for both the subprocess CLI path and the
frozen in-process path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def save_audio(
    wav: Any,
    path: str | Path,
    samplerate: int,
    bitrate: int = 320,
    clip: str = "rescale",
    bits_per_sample: int = 16,
    as_float: bool = False,
    preset: int = 2,
) -> None:
    """Drop-in replacement for ``demucs.audio.save_audio`` using soundfile.

    ``demucs`` passes a ``(channels, samples)`` torch tensor.  ``soundfile``
    expects ``(samples, channels)``.  ``bitrate``/``preset`` only apply to the
    MP3 path in Demucs and are accepted for signature compatibility.
    """
    import soundfile as sf

    array = wav.detach().cpu().numpy() if hasattr(wav, "detach") else np.asarray(wav)
    array = np.asarray(array, dtype=np.float32)
    if array.ndim == 2:
        array = array.T
    elif array.ndim == 1:
        array = array[:, None]

    if clip == "rescale":
        peak = float(np.max(np.abs(array))) if array.size else 0.0
        if peak > 0:
            array = array / peak * 0.99
    elif clip == "clamp":
        array = np.clip(array, -1.0, 1.0)
    elif clip == "tanh":
        array = np.tanh(array)

    subtype = "FLOAT" if as_float else {16: "PCM_16", 24: "PCM_24", 32: "PCM_32"}.get(
        int(bits_per_sample), "PCM_16"
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), array, int(samplerate), subtype=subtype)


def install_soundfile_writer() -> None:
    """Point Demucs' module-level ``save_audio`` references at soundfile."""
    import demucs.audio
    import demucs.separate

    demucs.audio.save_audio = save_audio  # type: ignore[assignment]
    demucs.separate.save_audio = save_audio  # type: ignore[assignment]


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``python -m audio_to_tab.demucs_bootstrap``."""
    import sys

    from demucs.separate import main as demucs_main

    install_soundfile_writer()
    sys.argv = ["demucs", *(argv if argv is not None else sys.argv[1:])]
    try:
        demucs_main()
    except SystemExit as exc:  # argparse / demucs uses SystemExit for errors
        if exc.code not in (0, None):
            raise


if __name__ == "__main__":
    main()
