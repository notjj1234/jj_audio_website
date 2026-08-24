"""Demucs stem separation for isolating guitar from full mixes."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from audio_to_tab.subprocess_util import subprocess_run_kwargs

logger = logging.getLogger(__name__)

GUITAR_FT_CHECKPOINT_ID = "htdemucs_6s_guitar_ft"
GUITAR_FT_HF_REPO = "adityalakhani/htdemucs-6s-guitar-ft"
GUITAR_FT_FILENAME = "guitar_htdemucs_6s.pt"
GUITAR_FT_URL = (
    f"https://huggingface.co/{GUITAR_FT_HF_REPO}/resolve/main/{GUITAR_FT_FILENAME}"
)
SUPPORTED_GUITAR_CHECKPOINTS = frozenset({GUITAR_FT_CHECKPOINT_ID})


def is_demucs_available() -> bool:
    """Return True if the Demucs package is importable."""
    try:
        import demucs  # noqa: F401

        return True
    except ImportError:
        return False


def _torch_cache_dir() -> Path:
    if env := os.environ.get("TORCH_HOME"):
        return Path(env)
    return Path.home() / ".cache" / "torch"


def guitar_ft_weights_path() -> Path:
    """Local cache path for the community guitar-ft HTDemucs-6s weights."""
    return _torch_cache_dir() / "checkpoints" / GUITAR_FT_FILENAME


def download_guitar_ft_weights(*, force: bool = False) -> Path:
    """Download guitar-ft weights into the torch cache (urllib, no huggingface_hub)."""
    path = guitar_ft_weights_path()
    if path.exists() and not force:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    try:
        with urllib.request.urlopen(GUITAR_FT_URL, timeout=120) as resp:
            data = resp.read()
        tmp.write_bytes(data)
        tmp.replace(path)
    except (urllib.error.URLError, OSError) as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to download guitar-ft weights from {GUITAR_FT_URL}") from exc
    return path


def guitar_ft_weights_sha256(path: Path | None = None) -> str:
    """Return sha256 hex digest of cached guitar-ft weights (for pinning/tests)."""
    target = path or guitar_ft_weights_path()
    digest = hashlib.sha256()
    with target.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_guitar_ft_state_dict(weights_path: Path):
    """Load guitar-ft checkpoint state dict onto CPU."""
    import torch

    checkpoint = torch.load(weights_path, map_location="cpu", weights_only=True)
    if isinstance(checkpoint, dict):
        if "model_state_dict" in checkpoint:
            return checkpoint["model_state_dict"]
        if "state" in checkpoint:
            return checkpoint["state"]
    return checkpoint


def run_demucs_guitar_ft_inprocess(
    audio_path: Path,
    output_root: Path,
    *,
    device: str = "cpu",
    quality: str = "fast",
) -> None:
    """
    Run official HTDemucs-6s with community guitar-ft weights in-process.

    Writes the same six stem filenames Demucs CLI would produce under
    ``output_root/htdemucs_6s/<track>/``.
    """
    import torch
    import torchaudio
    from demucs.apply import apply_model
    from demucs.audio import convert_audio, save_audio
    from demucs.pretrained import get_model

    weights_path = download_guitar_ft_weights()
    model = get_model("htdemucs_6s")
    model.load_state_dict(load_guitar_ft_state_dict(weights_path))
    model.eval()

    dev_name = device
    if dev_name == "cuda" and not torch.cuda.is_available():
        dev_name = "cpu"
    dev = torch.device(dev_name)
    model.to(dev)

    shifts = int({"fast": 0, "balanced": 1, "high": 3, "extreme": 5}.get(quality, 0))
    overlap = {"fast": 0.25, "balanced": 0.25, "high": 0.5, "extreme": 0.75}.get(
        quality, 0.25
    )

    wav, sr = torchaudio.load(str(audio_path))
    wav = convert_audio(wav, sr, model.samplerate, model.audio_channels)
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / (ref.std() + 1e-8)

    with torch.no_grad():
        sources = apply_model(
            model,
            wav[None],
            device=dev,
            shifts=shifts,
            overlap=overlap,
            progress=False,
        )[0]
    sources = sources * ref.std() + ref.mean()

    track_name = audio_path.stem
    out_dir = output_root / "htdemucs_6s" / track_name
    out_dir.mkdir(parents=True, exist_ok=True)
    for source, name in zip(sources, model.sources):
        save_audio(source, str(out_dir / f"{name}.wav"), samplerate=model.samplerate)


def run_demucs(demucs_args: list[str]) -> None:
    """
    Run Demucs with CLI-style args (everything after ``python -m demucs``).

    When frozen (PyInstaller), invokes ``demucs.separate.main`` in-process because
    ``sys.executable`` is the app binary and cannot run ``-m demucs``.
    Otherwise uses a subprocess so tests and local runs keep the same isolation.
    """
    if getattr(sys, "frozen", False):
        from demucs.separate import main as demucs_main

        try:
            demucs_main(demucs_args)
        except SystemExit as exc:
            code = exc.code
            if code not in (0, None):
                raise RuntimeError(f"Demucs failed with exit code {code}") from exc
        return

    cmd = [sys.executable, "-m", "demucs", *demucs_args]
    result = subprocess.run(cmd, capture_output=True, text=True, **subprocess_run_kwargs())
    if result.returncode != 0:
        raise RuntimeError(f"Demucs failed: {result.stderr or result.stdout}")


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
    overlap = {"fast": "0.25", "balanced": "0.25", "high": "0.5", "extreme": "0.75"}.get(
        quality, "0.25"
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_demucs(
            [
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
        )

        guitar_files = list(tmp_path.rglob("guitar.wav"))
        if not guitar_files:
            raise FileNotFoundError(
                "Demucs did not produce a guitar stem. "
                "Ensure model supports guitar separation (htdemucs_6s)."
            )

        shutil.copy2(guitar_files[0], out)

    return out
