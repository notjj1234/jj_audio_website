"""Upload validation helpers."""

from __future__ import annotations

import mimetypes
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
    "application/octet-stream",  # browsers sometimes send this; extension still checked
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
    if ctype and ctype not in ALLOWED_MIME_EXACT and not any(
        ctype.startswith(p) for p in ALLOWED_MIME_PREFIXES
    ):
        # Guess from extension as a soft fallback
        guessed, _ = mimetypes.guess_type(name)
        if guessed and guessed.startswith("audio/"):
            return True, ""
        return False, f"Unsupported content type '{ctype}'"
    return True, ""
