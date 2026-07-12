"""Audio ingestion and normalization."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def _require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required but not found on PATH")
    return ffmpeg


def normalize_audio(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Convert audio to 44.1kHz stereo WAV suitable for ML models."""
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Audio file not found: {src}")

    if output_path is None:
        out = Path(tempfile.mkstemp(suffix=".wav", prefix="audio_norm_")[1])
    else:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = _require_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-ar",
        "44100",
        "-ac",
        "2",
        "-sample_fmt",
        "s16",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    return out


def download_youtube_audio(url: str, output_dir: str | Path) -> Path:
    """Download audio from YouTube via yt-dlp."""
    import yt_dlp

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    template = str(out_dir / "%(title).80s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "youtube_audio")
        # yt-dlp writes .wav after postprocess
        candidates = list(out_dir.glob("*.wav"))
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
        # fallback search by title
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title[:80])
        for p in out_dir.iterdir():
            if safe[:20] in p.stem:
                return normalize_audio(p)
        raise FileNotFoundError(f"Downloaded audio not found for: {url}")
