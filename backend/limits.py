"""Upload validation helpers."""

from __future__ import annotations

from pathlib import Path

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".mpeg", ".mp4"}
ALLOWED_MIME_PREFIXES = ("audio/",)
ALLOWED_MIME_EXACT = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/flac",
    "audio/x-flac",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    "video/mp4",  # m4a/mp4 containers
    "application/octet-stream",  # allowed only when magic bytes match
}


def normalize_filename(filename: str) -> str:
    name = Path(filename or "audio.wav").name
    if not name or name in {".", ".."}:
        return "audio.wav"
    return name


def is_allowed_upload(filename: str, content_type: str | None) -> tuple[bool, str]:
    name = normalize_filename(filename)
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"

    ctype = (content_type or "").split(";")[0].strip().lower()
    if not ctype:
        return True, ""
    if ctype in ALLOWED_MIME_EXACT or any(ctype.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        return True, ""
    return False, f"Unsupported content type '{ctype}'"


def is_audio_magic(header: bytes) -> bool:
    """Return True if the file header looks like WAV, FLAC, MP3, or MP4/M4A."""
    if len(header) < 12:
        return False
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return True
    if header.startswith(b"fLaC"):
        return True
    if header.startswith(b"ID3"):
        return True
    # MPEG audio frame sync (MP3 without ID3)
    if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return True
    # ISO BMFF (mp4 / m4a): size + 'ftyp'
    if header[4:8] == b"ftyp":
        return True
    return False


def is_allowed_audio_content(header: bytes) -> tuple[bool, str]:
    if is_audio_magic(header):
        return True, ""
    return False, "File does not look like audio"
