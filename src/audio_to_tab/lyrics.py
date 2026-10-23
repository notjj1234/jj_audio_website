"""Local-only lyrics transcription with pinned faster-whisper weights.

The module imports without ``faster-whisper`` installed. Runtime never touches the network: the
model is read from a local directory, and the optional downloader uses the existing
``download_sha256_file`` helper with the hashes below.

Word timestamps are best-effort. When a segment has no words, the line is still returned (the UI
shows line-level lyrics); when a line is longer than ``MAX_LINE_SEC`` with words, it is chunked for
display without changing the underlying timing.
"""

from __future__ import annotations

import logging
import math
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from audio_to_tab.analysis import LyricLine, LyricWord
from audio_to_tab.roformer import download_sha256_file, file_sha256

logger = logging.getLogger(__name__)

MODEL_REPO = "Systran/faster-whisper-small"
MODEL_BASE_URL = f"https://huggingface.co/{MODEL_REPO}/resolve/main"
MODEL_FILES: dict[str, tuple[str, int]] = {
    "model.bin": (
        "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
        483546902,
    ),
    "config.json": (
        "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828",
        2370,
    ),
    "tokenizer.json": (
        "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
        2203239,
    ),
    "vocabulary.txt": (
        "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
        459861,
    ),
}
_DEFAULT_DIR = Path.home() / ".cache" / "audio_to_tab" / "analysis" / "faster-whisper-small"
_MAX_LINE_SEC = 8.0
_MAX_LINE_WORDS = 12


def default_model_dir() -> Path:
    configured = os.environ.get("ATT_LYRICS_MODEL_DIR")
    return Path(configured) if configured else _DEFAULT_DIR


def _faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def _files_present(model_dir: Path) -> bool:
    return all(
        (model_dir / name).is_file() and (model_dir / name).stat().st_size > 0
        for name in MODEL_FILES
    )


def lyrics_available(model_dir: Path | None = None) -> bool:
    """True when the local model files and the optional dependency are both present."""
    path = Path(model_dir) if model_dir is not None else default_model_dir()
    return _files_present(path) and _faster_whisper_available()


def ensure_lyrics_model(
    model_dir: Path | None = None,
    *,
    progress: Callable[[str], None] | None = None,
) -> Path:
    """Download missing/incorrect pinned files into ``model_dir`` and return it."""
    path = Path(model_dir) if model_dir is not None else default_model_dir()
    path.mkdir(parents=True, exist_ok=True)
    for name, (expected_sha, _) in MODEL_FILES.items():
        destination = path / name
        try:
            if destination.is_file() and file_sha256(destination) == expected_sha:
                continue
        except OSError:
            pass
        _notify(progress, f"lyrics: downloading {name}")
        download_sha256_file(f"{MODEL_BASE_URL}/{name}", destination, expected_sha, timeout=600)
    return path


def _notify(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is None:
        return
    try:
        progress(message)
    except Exception:
        logger.debug("Lyrics progress callback failed", exc_info=True)


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _clamp(value: Any, duration: float | None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    if duration is not None and duration > 0:
        number = min(number, duration)
    return number


def _line_from_words(words: list[LyricWord], fallback_text: str = "") -> LyricLine | None:
    if not words:
        return None
    text = " ".join(word.text for word in words).strip() or fallback_text.strip()
    if not text:
        return None
    return LyricLine(
        start=words[0].start,
        end=words[-1].end,
        text=text,
        words=tuple(words),
    )


def _split_long_lines(lines: list[LyricLine]) -> list[LyricLine]:
    output: list[LyricLine] = []
    for line in lines:
        if not line.words or line.end - line.start <= _MAX_LINE_SEC:
            output.append(line)
            continue
        chunk: list[LyricWord] = []
        for word in line.words:
            if chunk and (
                word.end - chunk[0].start > _MAX_LINE_SEC or len(chunk) >= _MAX_LINE_WORDS
            ):
                split = _line_from_words(chunk, line.text)
                if split is not None:
                    output.append(split)
                chunk = []
            chunk.append(word)
        if chunk:
            split = _line_from_words(chunk, line.text)
            if split is not None:
                output.append(split)
    return output


def transcribe_lyrics(
    audio_path: Path,
    *,
    model_dir: Path | None = None,
    language: str | None = None,
    progress: Callable[[str], None] | None = None,
    duration_sec: float | None = None,
    transcriber: Any | None = None,
) -> tuple[list[LyricLine], str | None, list[str]]:
    """Transcribe ``audio_path`` into word-timed lines; never raises on model/audio failure.

    ``transcriber`` is for tests or a preloaded model. When omitted, a CPU int8 Whisper model is
    loaded lazily from ``model_dir`` (or the default cache).
    """
    path = Path(audio_path)
    if not path.is_file():
        return [], None, [f"lyrics audio not found: {path}"]
    if path.stat().st_size == 0:
        return [], None, [f"lyrics audio is empty: {path}"]

    model_path = Path(model_dir) if model_dir is not None else default_model_dir()
    if transcriber is None:
        if not _files_present(model_path):
            return [], None, [f"lyrics model not found or incomplete: {model_path}"]
        if not _faster_whisper_available():
            return [], None, ["faster-whisper is not installed"]
        try:
            from faster_whisper import WhisperModel

            _notify(progress, "lyrics: loading model")
            transcriber = WhisperModel(str(model_path), device="cpu", compute_type="int8")
        except Exception as exc:
            logger.warning("Lyrics model load failed: %s", exc)
            return [], None, [f"lyrics model failed to load: {exc}"]

    _notify(progress, "lyrics: transcribing")
    try:
        segments, info = transcriber.transcribe(
            str(path),
            word_timestamps=True,
            vad_filter=True,
            language=language,
            beam_size=5,
        )
    except Exception as exc:
        logger.warning("Lyrics transcription failed: %s", exc)
        return [], None, [f"lyrics transcription failed: {exc}"]

    duration = _positive_float(duration_sec) or _positive_float(getattr(info, "duration", None))
    detected_language = getattr(info, "language", None) or language
    lines: list[LyricLine] = []
    transcription_error: str | None = None
    try:
        for segment in segments:
            raw_words = getattr(segment, "words", None) or []
            words: list[LyricWord] = []
            for raw in raw_words:
                text = str(getattr(raw, "word", "") or "").strip()
                if not text:
                    continue
                start = _clamp(getattr(raw, "start", None), duration)
                end = _clamp(getattr(raw, "end", None), duration)
                if start is None or end is None or end < start:
                    continue
                words.append(LyricWord(start=start, end=end, text=text))
            words.sort(key=lambda word: (word.start, word.end))

            text = str(getattr(segment, "text", "") or "").strip()
            if words:
                start = words[0].start
                end = words[-1].end
            else:
                start = _clamp(getattr(segment, "start", None), duration)
                end = _clamp(getattr(segment, "end", None), duration)
            if start is None or end is None or end < start:
                continue
            if not text and not words:
                continue
            if not text:
                text = " ".join(word.text for word in words)
            lines.append(
                LyricLine(
                    start=start,
                    end=end,
                    text=text,
                    words=tuple(words),
                )
            )
    except Exception as exc:
        # faster-whisper yields segments lazily, so a decode error can surface
        # here rather than at the transcribe() call. Keep the lines we got.
        logger.warning("Lyrics transcription stopped early: %s", exc)
        transcription_error = f"lyrics transcription stopped early: {exc}"

    lines.sort(key=lambda line: (line.start, line.end))
    lines = _split_long_lines(lines)
    warnings: list[str] = []
    if transcription_error is not None:
        warnings.append(transcription_error)
    if not lines:
        warnings.append("no lyrics detected")
    elif not any(line.words for line in lines):
        warnings.append("word timestamps unavailable; showing line-level lyrics")
    _notify(progress, f"lyrics: {len(lines)} lines")
    return lines, str(detected_language) if detected_language else None, warnings


__all__ = [
    "MODEL_FILES",
    "default_model_dir",
    "ensure_lyrics_model",
    "lyrics_available",
    "transcribe_lyrics",
]
