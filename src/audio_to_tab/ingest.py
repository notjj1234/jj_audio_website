"""Audio ingestion and normalization."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from audio_to_tab.subprocess_util import subprocess_run_kwargs

logger = logging.getLogger(__name__)

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


class YouTubeSearchError(RuntimeError):
    """User-facing failure searching public YouTube videos (no API key)."""


class _YoutubeFileLogger:
    """Router all yt-dlp output to a per-download log file (any platform)."""

    def __init__(self, path: Path):
        self._path = path

    def _write(self, level: str, msg: str) -> None:
        try:
            with self._path.open("a", encoding="utf-8") as log:
                log.write(f"[{level}] {msg}\n")
        except OSError:
            import sys

            sys.stderr.write(f"[yt-dlp] could not write log to {self._path}\n")

    def debug(self, msg: str) -> None:
        self._write("debug", str(msg))

    def info(self, msg: str) -> None:
        self._write("info", str(msg))

    def warning(self, msg: str) -> None:
        self._write("warning", str(msg))

    def error(self, msg: str) -> None:
        self._write("error", str(msg))


@dataclass(frozen=True)
class YouTubeSearchHit:
    """One public video from a no-API yt-dlp search."""

    video_id: str
    title: str
    channel: str
    duration_sec: int | None
    url: str
    thumbnail_url: str


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
    elif sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = Path(base) / "AudioTools" / "logs"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "AudioTools" / "logs"
    else:
        base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
        path = Path(base) / "audiotools" / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path / "yt-dlp.log"


def _youtube_ydl_opts(
    *,
    template: str,
    player_client: str,
    verbose: bool = False,
    log_path: Path | None = None,
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
    if verbose and log_path is not None:
        opts["logger"] = _YoutubeFileLogger(log_path)
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
    except Exception as exc:
        logger.debug("yt-dlp cache clear failed: %s", exc)


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


def _title_stem(name: str) -> str:
    """Canonical filename-stem form (case- and punctuation-insensitive)."""
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def _normalize_in_place(wav: Path) -> Path:
    """Normalize ``wav`` into a same-dir temp, then atomically move it back.

    Keeps the real file name (e.g. the YouTube video title) on the result so
    callers that use ``path.stem`` show the human title instead of the
    ``audio_norm_*`` temp name.
    """
    fd, name = tempfile.mkstemp(dir=str(wav.parent), prefix=".audio_norm_", suffix=".wav")
    os.close(fd)
    temp = Path(name)
    try:
        normalize_audio(wav, output_path=temp)
        try:
            temp.replace(wav)
        except OSError:
            shutil.move(str(temp), str(wav))
    finally:
        _unlink_quiet(temp)
    return wav


def _resolve_downloaded_wav(out_dir: Path, title: str, url: str) -> Path:
    safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in (title or "")).strip()[:80]
    if safe:
        want = _title_stem(safe)
        matches = [
            p for p in out_dir.glob("*.wav") if _title_stem(p.stem) == want
        ]
        if matches:
            return _normalize_in_place(max(matches, key=lambda p: p.stat().st_mtime))

    candidates = list(out_dir.glob("*.wav"))
    if candidates:
        return _normalize_in_place(max(candidates, key=lambda p: p.stat().st_mtime))
    raise FileNotFoundError(f"Downloaded audio not found for: {url}")


def format_youtube_duration(seconds: int | None) -> str:
    """Compact ``m:ss`` / ``h:mm:ss`` label; empty when duration is unknown."""
    if seconds is None:
        return ""
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return ""
    if total < 0:
        return ""
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _watch_url_from_entry(entry: dict) -> str | None:
    """Build a normal watch URL from a yt-dlp flat or full search entry."""
    webpage = (entry.get("webpage_url") or entry.get("original_url") or "").strip()
    if is_youtube_url(webpage):
        return webpage
    raw_url = (entry.get("url") or "").strip()
    if is_youtube_url(raw_url):
        return raw_url
    video_id = (entry.get("id") or "").strip()
    if not video_id and raw_url and not raw_url.startswith("http"):
        video_id = raw_url
    if video_id and all(c.isalnum() or c in "-_" for c in video_id):
        return f"https://www.youtube.com/watch?v={video_id}"
    return None


def _thumbnail_url_for_entry(entry: dict, video_id: str) -> str:
    """Prefer yt-dlp thumbnail fields; else public CDN hqdefault for the id."""
    direct = (entry.get("thumbnail") or "").strip()
    if direct.startswith(("http://", "https://")):
        return direct
    thumbs = entry.get("thumbnails")
    if isinstance(thumbs, list):
        for thumb in reversed(thumbs):
            if not isinstance(thumb, dict):
                continue
            url = (thumb.get("url") or "").strip()
            if url.startswith(("http://", "https://")):
                return url
    vid = (video_id or "").strip()
    if vid and all(c.isalnum() or c in "-_" for c in vid):
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return ""


def search_youtube_videos(query: str, *, max_results: int = 5) -> list[YouTubeSearchHit]:
    """Search public YouTube videos via yt-dlp (no API key).

    Uses ``ytsearchN:query``. Returns watch URLs compatible with
    ``download_youtube_audio``.
    """
    q = (query or "").strip()
    if not q:
        raise ValueError("Enter a search query")
    limit = max(1, min(int(max_results), 10))
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{q}", download=False)
    except Exception as exc:
        detail = str(exc).strip() or "unknown error"
        raise YouTubeSearchError(
            "Could not search YouTube. Check your connection and try again. "
            f"Details: {detail}"
        ) from exc

    entries = (info or {}).get("entries") or []
    hits: list[YouTubeSearchHit] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = _watch_url_from_entry(entry)
        if not url:
            continue
        video_id = (entry.get("id") or "").strip()
        if not video_id:
            video_id = (parse_qs(urlparse(url).query).get("v") or [""])[0].strip()
        if not video_id:
            continue
        title = (entry.get("title") or "Untitled").strip() or "Untitled"
        channel = (
            entry.get("channel")
            or entry.get("uploader")
            or entry.get("creator")
            or ""
        )
        channel = str(channel).strip()
        duration_raw = entry.get("duration")
        try:
            duration_sec = int(duration_raw) if duration_raw is not None else None
        except (TypeError, ValueError):
            duration_sec = None
        hits.append(
            YouTubeSearchHit(
                video_id=video_id,
                title=title,
                channel=channel,
                duration_sec=duration_sec,
                url=url,
                thumbnail_url=_thumbnail_url_for_entry(entry, video_id),
            )
        )
        if len(hits) >= limit:
            break
    return hits


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
            for stale in out_dir.glob("*.wav"):
                _unlink_quiet(stale)
            for stale in out_dir.glob("*.part"):
                _unlink_quiet(stale)
        opts = _youtube_ydl_opts(
            template=template,
            player_client=player_client,
            verbose=verbose,
            log_path=log_path,
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
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


def _unlink_quiet(path: Path) -> None:
    with suppress(OSError):
        path.unlink()


def temporary_output_path(prefix: str, suffix: str) -> Path:
    """Create a caller-owned temp output path for audio writing tools.

    ``tempfile.mkstemp`` hands back an open FD that engine functions never read
    or write (they pass the path to ffmpeg instead); closing it right away is
    required on Windows — an open FD makes later ``unlink()`` calls fail with
    ``PermissionError`` and leaks the handle. The caller owns the file (and its
    deletion) once returned.
    """
    fd, name = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    return Path(name)


def normalize_audio(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Convert audio to canonical WAV for ML models. Output format is fixed at 44.1kHz stereo 16-bit WAV (required by ML models)."""
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Audio file not found: {src}")

    temp_out = output_path is None
    if temp_out:
        out = temporary_output_path("audio_norm_", ".wav")
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
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, **subprocess_run_kwargs())
    except BaseException:
        if temp_out:
            _unlink_quiet(out)
        raise
    if result.returncode != 0:
        if temp_out:
            _unlink_quiet(out)
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    return out
