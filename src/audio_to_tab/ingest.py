"""Audio ingestion and normalization."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from audio_to_tab.subprocess_util import subprocess_run_kwargs

_YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
)

# yt-dlp extractor-args retry ladder for public videos (YouTube 403 / SABR).
# Attempt 1: skip android_sdkless (often 403). Attempt 2: web_safari HLS + tv_embedded.
_YOUTUBE_PLAYER_CLIENTS = (
    "default,-android_sdkless",
    "web_safari,tv_embedded,-android_sdkless",
)


class YouTubeDownloadError(RuntimeError):
    """User-facing failure downloading public YouTube audio."""


def is_youtube_url(url: str) -> bool:
    """Return True if ``url`` is an http(s) YouTube link."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if host in _YOUTUBE_HOSTS:
        return True
    return host.endswith(".youtube.com")


def _require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required but not found on PATH")
    return ffmpeg


def _youtube_debug_enabled() -> bool:
    return os.environ.get("AUDIO_TOOLS_DEBUG", "").strip() in {"1", "true", "TRUE", "yes"}


def _youtube_log_path() -> Path | None:
    """Write verbose yt-dlp output when debugging or a desktop log dir exists."""
    if not _youtube_debug_enabled():
        return None
    override = os.environ.get("AUDIO_TOOLS_LOG_DIR", "").strip()
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path / "yt-dlp.log"
    if sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "AudioTools" / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path / "yt-dlp.log"
    return None


def _youtube_ydl_opts(
    *,
    template: str,
    player_client: str,
    verbose: bool = False,
) -> dict:
    """yt-dlp options for one public-video download attempt."""
    ffmpeg = shutil.which("ffmpeg")
    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "extractor_args": {
            "youtube": {
                "player_client": [part.strip() for part in player_client.split(",") if part.strip()],
            }
        },
        "quiet": not verbose,
        "no_warnings": not verbose,
        "verbose": verbose,
    }
    if ffmpeg:
        opts["ffmpeg_location"] = str(Path(ffmpeg).resolve().parent)
    return opts


def _is_403_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "403" in text or "unable to download video data" in text or "forbidden" in text


def _clear_ytdlp_cache() -> None:
    """Drop a stale player cache that often produces 403s after YouTube updates."""
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL({"rm_cachedir": True, "quiet": True}) as ydl:
            ydl.cache.remove()
    except Exception:
        pass


def _user_facing_youtube_error(last_exc: BaseException | None) -> YouTubeDownloadError:
    detail = str(last_exc).strip() if last_exc else "unknown error"
    parts = [
        "Could not download this YouTube video.",
        "Only public videos work (no login).",
        "Upload the audio file instead.",
    ]
    if _is_403_error(last_exc or Exception("")):
        parts.append("YouTube rejected the download (HTTP 403).")
    parts.append(f"Details: {detail}")
    return YouTubeDownloadError(" ".join(parts))


def _resolve_downloaded_wav(out_dir: Path, title: str, url: str) -> Path:
    candidates = list(out_dir.glob("*.wav"))
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title[:80])
    for p in out_dir.iterdir():
        if safe[:20] in p.stem:
            return normalize_audio(p)
    raise FileNotFoundError(f"Downloaded audio not found for: {url}")


def download_youtube_audio(url: str, output_dir: str | Path) -> Path:
    """Download audio from a public YouTube URL via yt-dlp.

    Retries with alternate player clients and a cache clear after HTTP 403.
    """
    if not is_youtube_url(url):
        raise ValueError("Only YouTube URLs are allowed")
    import yt_dlp

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    template = str(out_dir / "%(title).80s.%(ext)s")
    verbose = _youtube_debug_enabled()
    log_path = _youtube_log_path()
    last_exc: BaseException | None = None

    for index, player_client in enumerate(_YOUTUBE_PLAYER_CLIENTS):
        if index > 0:
            _clear_ytdlp_cache()
        opts = _youtube_ydl_opts(
            template=template,
            player_client=player_client,
            verbose=verbose,
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                if log_path is not None:
                    ydl.params["logger"] = None
                info = ydl.extract_info(url, download=True)
            title = (info or {}).get("title", "youtube_audio")
            return _resolve_downloaded_wav(out_dir, title, url)
        except ValueError:
            raise
        except Exception as exc:
            last_exc = exc
            if log_path is not None:
                try:
                    with log_path.open("a", encoding="utf-8") as log:
                        log.write(f"{url}\n{player_client}\n{exc}\n\n")
                except OSError:
                    pass
            if not _is_403_error(exc) or index == len(_YOUTUBE_PLAYER_CLIENTS) - 1:
                raise _user_facing_youtube_error(exc) from exc
            continue

    raise _user_facing_youtube_error(last_exc)


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
    result = subprocess.run(cmd, capture_output=True, text=True, **subprocess_run_kwargs())
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    return out
