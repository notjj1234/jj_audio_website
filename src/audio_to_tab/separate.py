"""Demucs stem separation for isolating guitar from full mixes."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def is_demucs_available() -> bool:
    """Return True if the Demucs package is importable."""
    try:
        import demucs  # noqa: F401

        return True
    except ImportError:
        return False


def separate_guitar_stem(
    audio_path: str | Path,
    output_path: str | Path | None = None,
    *,
    model: str = "htdemucs_6s",
    device: str = "cpu",
    quality: str = "fast",
) -> Path:
    """
    Extract guitar stem using Demucs CLI.

    quality presets mirror TabGrabber: fast | balanced | high | extreme
    """
    if not is_demucs_available():
        raise RuntimeError(
            "Demucs is not installed. Install with: pip install -r requirements-demucs.txt"
        )

    src = Path(audio_path)
    if output_path is None:
        out = Path(tempfile.mkstemp(suffix="_guitar.wav", prefix="stem_")[1])
    else:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

    shifts = {"fast": "0", "balanced": "1", "high": "3", "extreme": "5"}.get(quality, "0")
    overlap = {"fast": "0.25", "balanced": "0.25", "high": "0.5", "extreme": "0.75"}.get(quality, "0.25")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cmd = [
            sys.executable,
            "-m",
            "demucs",
            "-n",
            model,
            "-d",
            device,
            "-o",
            str(tmp_path),
            "--shifts",
            shifts,
            "--overlap",
            overlap,
            str(src),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Demucs failed: {result.stderr or result.stdout}")

        guitar_files = list(tmp_path.rglob("guitar.wav"))
        if not guitar_files:
            raise FileNotFoundError(
                "Demucs did not produce a guitar stem. "
                "Ensure model supports guitar separation (htdemucs_6s)."
            )

        shutil.copy2(guitar_files[0], out)

    return out
