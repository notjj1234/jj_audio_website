"""Multi-stem audio isolation via Demucs (standalone feature)."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from audio_to_tab.ingest import normalize_audio
from audio_to_tab.separate import is_demucs_available

DEMUCS_INSTALL_HINT = (
    "Demucs is required for stem separation. Install with: make install-demucs "
    "or pip install -e \".[demucs]\""
)

ProgressCallback = Callable[[str, str], None]

SUPPORTED_MODELS = ("htdemucs_6s", "htdemucs", "htdemucs_ft")

QUALITY_SHIFTS = {"fast": "0", "balanced": "1", "high": "3", "extreme": "5"}
QUALITY_OVERLAP = {"fast": "0.25", "balanced": "0.25", "high": "0.5", "extreme": "0.75"}


@dataclass
class DualGuitarDiagnostics:
    """Result of stereo heuristic on a separated guitar stem."""

    attempted: bool
    split: bool
    reason: str
    correlation: float | None = None
    balance_ratio: float | None = None


@dataclass
class IsolateConfig:
    model: str = "htdemucs_6s"
    quality: str = "balanced"
    device: str = "cpu"
    max_duration_sec: float | None = 90.0
    two_stems: str | None = None  # e.g. "vocals" for karaoke-style split
    dual_guitar: bool = False  # experimental stereo split of guitar -> guitar1/guitar2


def _noop_progress(stage: str, message: str) -> None:
    pass


def _load_stereo(path: Path) -> tuple[np.ndarray, int]:
    import soundfile as sf

    data, sr = sf.read(str(path), always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    return data.astype(np.float32), sr


def analyze_dual_guitar_candidate(guitar_path: Path) -> DualGuitarDiagnostics:
    """Heuristic: stereo guitar stem with distinct L/R content may be two guitars."""
    if not guitar_path.exists():
        return DualGuitarDiagnostics(False, False, "guitar stem missing")

    data, _sr = _load_stereo(guitar_path)
    if data.shape[1] < 2 or len(data) < 1024:
        return DualGuitarDiagnostics(True, False, "guitar stem is mono or too short")

    left = data[:, 0]
    right = data[:, 1]
    rms_l = float(np.sqrt(np.mean(left**2)))
    rms_r = float(np.sqrt(np.mean(right**2)))
    max_rms = max(rms_l, rms_r, 1e-9)
    balance = min(rms_l, rms_r) / max_rms

    if balance < 0.12:
        return DualGuitarDiagnostics(
            True,
            False,
            "stereo energy too imbalanced for dual-guitar split",
            balance_ratio=balance,
        )

    if np.std(left) < 1e-6 or np.std(right) < 1e-6:
        return DualGuitarDiagnostics(True, False, "near-silent channel", balance_ratio=balance)

    corr = float(np.corrcoef(left, right)[0, 1])
    if corr > 0.92:
        return DualGuitarDiagnostics(
            True,
            False,
            "L/R channels too similar (likely one guitar)",
            correlation=corr,
            balance_ratio=balance,
        )

    return DualGuitarDiagnostics(
        True,
        True,
        "stereo heuristic suggests two distinct guitar parts",
        correlation=corr,
        balance_ratio=balance,
    )


def split_dual_guitar_stem(
    guitar_path: Path,
    output_dir: Path,
) -> tuple[dict[str, Path], DualGuitarDiagnostics]:
    """
    Experimental: derive guitar1/guitar2 from stereo guitar stem.
    Never duplicates the file — uses L-dominant and R-dominant extraction.
    """
    import soundfile as sf

    diag = analyze_dual_guitar_candidate(guitar_path)
    if not diag.split:
        return {}, diag

    data, sr = _load_stereo(guitar_path)
    left = data[:, 0]
    right = data[:, 1]

  # Soft dominance masks reduce bleed from the opposite channel.
    guitar1_mono = np.where(np.abs(left) >= np.abs(right), left, left - 0.5 * right)
    guitar2_mono = np.where(np.abs(right) >= np.abs(left), right, right - 0.5 * left)
    guitar1 = np.column_stack([guitar1_mono, guitar1_mono])
    guitar2 = np.column_stack([guitar2_mono, guitar2_mono])

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    p1 = out_dir / "guitar1.wav"
    p2 = out_dir / "guitar2.wav"
    sf.write(str(p1), guitar1, sr, subtype="PCM_16")
    sf.write(str(p2), guitar2, sr, subtype="PCM_16")
    return {"guitar1": p1, "guitar2": p2}, diag


def _trim_audio(input_path: Path, max_duration_sec: float | None) -> Path:
    if max_duration_sec is None:
        return input_path
    out = input_path.parent / f"{input_path.stem}_trim.wav"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return input_path
    subprocess.run(
        [ffmpeg, "-y", "-i", str(input_path), "-t", str(max_duration_sec), str(out)],
        capture_output=True,
        check=False,
    )
    return out if out.exists() else input_path


def separate_stems(
    audio_path: str | Path,
    output_dir: str | Path,
    config: IsolateConfig | None = None,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Path]:
    """
    Separate an audio file into instrument stems using Demucs.

    Returns a mapping of stem name -> wav path under output_dir.
    CPU separation is slow (~track length or longer); quality presets multiply time.
    """
    if not is_demucs_available():
        raise RuntimeError(
            f"Demucs is not installed. {DEMUCS_INSTALL_HINT}"
        )

    cfg = config or IsolateConfig()
    if cfg.model not in SUPPORTED_MODELS:
        raise ValueError(
            f"Unsupported model {cfg.model!r}. Choose from: {', '.join(SUPPORTED_MODELS)}"
        )

    progress = on_progress or _noop_progress
    src = Path(audio_path)
    if not src.exists():
        raise FileNotFoundError(f"Audio file not found: {src}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    shifts = QUALITY_SHIFTS.get(cfg.quality, "0")
    overlap = QUALITY_OVERLAP.get(cfg.quality, "0.25")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        progress("ingest", "Normalizing audio")
        normalized = normalize_audio(src, tmp_path / "normalized.wav")
        progress("ingest", "Trimming audio" if cfg.max_duration_sec else "Using full audio")
        trimmed = _trim_audio(normalized, cfg.max_duration_sec)

        progress(
            "separate",
            f"Running Demucs ({cfg.model}, quality={cfg.quality}) — this can take a long time on CPU",
        )
        cmd = [
            sys.executable,
            "-m",
            "demucs",
            "-n",
            cfg.model,
            "-d",
            cfg.device,
            "-o",
            str(tmp_path / "demucs_out"),
            "--shifts",
            shifts,
            "--overlap",
            overlap,
        ]
        if cfg.two_stems:
            cmd.extend(["--two-stems", cfg.two_stems])
        cmd.append(str(trimmed))

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Demucs failed: {result.stderr or result.stdout}")

        progress("collect", "Collecting stem files")
        stem_files = list((tmp_path / "demucs_out").rglob("*.wav"))
        if not stem_files:
            raise FileNotFoundError("Demucs did not produce any stem wav files.")

        artifacts: dict[str, Path] = {}
        for stem_path in stem_files:
            name = stem_path.stem  # e.g. vocals, drums
            dest = out_dir / f"{name}.wav"
            shutil.copy2(stem_path, dest)
            artifacts[name] = dest

        if not artifacts:
            raise FileNotFoundError("No stems could be collected from Demucs output.")

        if cfg.dual_guitar and "guitar" in artifacts:
            progress("guitar_split", "Attempting experimental dual-guitar split")
            extra, diag = split_dual_guitar_stem(artifacts["guitar"], out_dir)
            if extra:
                artifacts.update(extra)
                progress("guitar_split", diag.reason)
            else:
                progress("guitar_split", f"Skipped dual-guitar: {diag.reason}")

        progress("done", f"Separated {len(artifacts)} stem(s)")
        return artifacts
