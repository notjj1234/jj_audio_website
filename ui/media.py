"""Media URL registration, preview encode, and mix-file cleanup for the isolate UI."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import soundfile as sf

from audio_to_tab.subprocess_util import subprocess_run_kwargs

# Prefer original WAVs under this duration; longer tracks use downsampled previews.
PREVIEW_DURATION_THRESHOLD_SEC = 90.0
# ~21 MB/min/stem float32 stereo @ 44.1kHz; 400MB ≈ ~3.2 stem-minutes at full rate.
PREVIEW_RAM_BUDGET_BYTES = 400 * 1024 * 1024
PREVIEW_SAMPLE_RATE = 22050
BYTES_PER_SEC_FULL = 44100 * 2 * 4  # float32 stereo estimate for RAM budgeting


def cleanup_mix_artifacts(run_dir: Path) -> None:
    """Remove leftover heard-mix and export mix files from a run directory."""
    if not run_dir.is_dir():
        return
    for path in run_dir.glob("_heard_mix_*.wav"):
        path.unlink(missing_ok=True)
    current = run_dir / "current_mix.wav"
    if current.exists():
        current.unlink(missing_ok=True)


def _stem_duration_sec(path: Path) -> float:
    info = sf.info(str(path))
    if info.samplerate <= 0:
        return 0.0
    return float(info.frames) / float(info.samplerate)


def should_use_previews(stem_paths: dict[str, Path]) -> bool:
    """True when stems are long enough that browser float buffers may be heavy."""
    if not stem_paths:
        return False
    durations = [_stem_duration_sec(p) for p in stem_paths.values() if p.exists()]
    if not durations:
        return False
    max_dur = max(durations)
    if max_dur > PREVIEW_DURATION_THRESHOLD_SEC:
        return True
    est_ram = len(stem_paths) * max_dur * BYTES_PER_SEC_FULL
    return est_ram > PREVIEW_RAM_BUDGET_BYTES


def _encode_preview_ffmpeg(src: Path, dest: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            "2",
            "-ar",
            str(PREVIEW_SAMPLE_RATE),
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
        **subprocess_run_kwargs(),
    )
    return result.returncode == 0 and dest.exists()


def ensure_mixer_audio_paths(stem_paths: dict[str, Path]) -> dict[str, Path]:
    """
    Return paths suitable for the browser mixer.

    Uses original WAVs when short; otherwise writes ``preview/<stem>.wav``
    (22.05 kHz stereo) once via ffmpeg. Falls back to originals if encode fails.
    """
    if not should_use_previews(stem_paths):
        return dict(stem_paths)

    run_dir = next(iter(stem_paths.values())).parent
    preview_dir = run_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for name, path in stem_paths.items():
        dest = preview_dir / f"{name}.wav"
        if dest.exists() and dest.stat().st_mtime >= path.stat().st_mtime:
            out[name] = dest
            continue
        if _encode_preview_ffmpeg(path, dest):
            out[name] = dest
        else:
            out[name] = path
    return out


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
