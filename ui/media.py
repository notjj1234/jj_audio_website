"""Media URL registration, preview encode, and mix-file cleanup for the isolate UI."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from audio_to_tab.subprocess_util import subprocess_run_kwargs

PREVIEW_SAMPLE_RATE = 44100


def cleanup_mix_artifacts(run_dir: Path) -> None:
    """Remove leftover heard-mix and export mix files from a run directory."""
    if not run_dir.is_dir():
        return
    for path in run_dir.glob("_heard_mix_*.wav"):
        path.unlink(missing_ok=True)
    current = run_dir / "current_mix.wav"
    if current.exists():
        current.unlink(missing_ok=True)


def ensure_mixer_audio_paths(stem_paths: dict[str, Path]) -> dict[str, Path]:
    """
    Return paths suitable for the browser mixer.

    Always uses the original stem WAVs (44.1 kHz). Downsampled 22.05 kHz
    previews stripped high end; do not bring them back.
    """
    return dict(stem_paths)


def media_url_for_file(path: Path, *, coordinates: str) -> str:
    """
    Register a file with Streamlit's media manager and return a browser-fetchable URL.

    Must be called during an active Streamlit script run.
    """
    from streamlit.runtime import get_instance

    runtime = get_instance()
    if runtime is None:
        raise RuntimeError("Streamlit runtime is not available")
    return runtime.media_file_mgr.add(
        str(path.resolve()),
        "audio/wav",
        coordinates,
        file_name=path.name,
    )


def stem_media_urls(stem_paths: dict[str, Path], *, coord_prefix: str = "isolate.mixer") -> dict[str, str]:
    """Register each stem and return ``{stem_id: media_url}``."""
    urls: dict[str, str] = {}
    for i, (name, path) in enumerate(sorted(stem_paths.items())):
        urls[name] = media_url_for_file(path, coordinates=f"{coord_prefix}.{i}.{name}")
    return urls


def register_mixer_media(stem_paths: dict[str, Path]) -> tuple[dict[str, str], dict[str, str]]:
    """Register playback + download stem URLs during the full page run.

    Registration must happen outside the ``@st.fragment``: fragment-scoped media
    registrations can be GC'd on a later full/fragment rerun, which makes stems
    intermittently fail to load in the mixer. Returning the URLs lets callers
    pass them into the fragment.
    """
    return (
        stem_media_urls(stem_paths),
        stem_media_urls(stem_paths, coord_prefix="isolate.download"),
    )


def region_preview_cache_key(
    fingerprint: str, start_sec: float, length_sec: float | None
) -> str:
    """Stable cache id: source fingerprint plus start/end (or full)."""
    digest = hashlib.sha256(fingerprint.encode("utf-8", errors="replace")).hexdigest()[:16]
    if length_sec is None:
        return f"{digest}_full"
    return f"{digest}_{float(start_sec):.3f}_{float(length_sec):.3f}"


def ensure_region_preview_wav(
    src: Path,
    *,
    start_sec: float,
    length_sec: float | None,
    fingerprint: str,
    cache_dir: Path,
) -> Path:
    """Return a wav whose duration is the isolate section, or ``src`` for a full file.

    Does not read the source into Python. Uses ffmpeg ``-ss`` before ``-i``.
    """
    if (length_sec is None or length_sec <= 0) and start_sec <= 0:
        return src
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{region_preview_cache_key(fingerprint, start_sec, length_sec)}.wav"
    try:
        if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
            return dest
    except OSError:
        pass
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return src
    cmd: list[str] = [
        ffmpeg,
        "-y",
        "-ss",
        str(float(start_sec)),
        "-i",
        str(src),
    ]
    if length_sec is not None and length_sec > 0:
        cmd.extend(["-t", str(float(length_sec))])
    cmd.extend(["-ac", "2", "-ar", str(PREVIEW_SAMPLE_RATE), str(dest)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        **subprocess_run_kwargs(),
    )
    if result.returncode == 0 and dest.exists():
        return dest
    return src
