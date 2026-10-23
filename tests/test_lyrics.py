"""Lyrics transcription tests: no model download, fake transcriber injection."""

from __future__ import annotations

from pathlib import Path

from audio_to_tab.lyrics import (
    MODEL_FILES,
    default_model_dir,
    ensure_lyrics_model,
    lyrics_available,
    transcribe_lyrics,
)


class FakeWord:
    def __init__(self, start: float, end: float, word: str) -> None:
        self.start = start
        self.end = end
        self.word = word


class FakeSegment:
    def __init__(self, start: float, end: float, text: str, words: list[FakeWord] | None) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.words = words


class FakeInfo:
    def __init__(self, language: str | None = "en", duration: float = 10.0) -> None:
        self.language = language
        self.duration = duration


class FakeTranscriber:
    def __init__(self, segments: list[FakeSegment], info: FakeInfo | None = None) -> None:
        self.segments = segments
        self.info = info or FakeInfo()
        self.kwargs: dict = {}

    def transcribe(self, path: str, **kwargs):
        self.kwargs = kwargs
        return iter(self.segments), self.info


def _audio(tmp_path, name: str = "vocals.wav") -> Path:
    path = tmp_path / name
    path.write_bytes(b"not-really-audio")
    return path


def test_missing_audio_returns_warning(tmp_path):
    lines, language, warnings = transcribe_lyrics(
        tmp_path / "nope.wav",
        model_dir=tmp_path,
        transcriber=FakeTranscriber([]),
    )

    assert lines == []
    assert language is None
    assert any("audio" in warning.lower() for warning in warnings)


def test_empty_audio_returns_warning(tmp_path):
    path = tmp_path / "empty.wav"
    path.write_bytes(b"")

    lines, _, warnings = transcribe_lyrics(path, model_dir=tmp_path, transcriber=FakeTranscriber([]))

    assert lines == []
    assert any("empty" in warning.lower() for warning in warnings)


def test_words_and_lines(tmp_path):
    audio = _audio(tmp_path)
    transcriber = FakeTranscriber(
        [
            FakeSegment(
                0.0,
                2.0,
                "hello world",
                [FakeWord(0.0, 1.0, "hello"), FakeWord(1.0, 2.0, " world")],
            )
        ],
        FakeInfo(language="en", duration=10.0),
    )

    lines, language, warnings = transcribe_lyrics(audio, model_dir=tmp_path, transcriber=transcriber)

    assert warnings == []
    assert language == "en"
    assert len(lines) == 1
    assert lines[0].text == "hello world"
    assert [word.text for word in lines[0].words] == ["hello", "world"]
    assert transcriber.kwargs["word_timestamps"] is True


def test_segment_only_returns_lines_without_words(tmp_path):
    audio = _audio(tmp_path)
    transcriber = FakeTranscriber([FakeSegment(1.0, 3.0, "line only", None)])

    lines, _, _ = transcribe_lyrics(audio, model_dir=tmp_path, transcriber=transcriber)

    assert len(lines) == 1
    assert lines[0].text == "line only"
    assert lines[0].words == ()


def test_clamps_and_drops_empty_words(tmp_path):
    audio = _audio(tmp_path)
    transcriber = FakeTranscriber(
        [
            FakeSegment(
                0.0,
                6.0,
                "keep",
                [
                    FakeWord(-1.0, 0.5, "bad-start"),
                    FakeWord(1.0, 20.0, "clamped"),
                    FakeWord(2.0, 3.0, "   "),
                    FakeWord(4.0, 3.0, "backwards"),
                ],
            )
        ],
        FakeInfo(duration=5.0),
    )

    lines, _, _ = transcribe_lyrics(
        audio,
        model_dir=tmp_path,
        transcriber=transcriber,
        duration_sec=5.0,
    )

    assert lines
    words = lines[0].words
    assert [word.text for word in words] == ["clamped"]
    assert words[0].end == 5.0
    assert all(0.0 <= word.start <= word.end <= 5.0 for word in words)


def test_long_segment_is_split_for_display(tmp_path):
    audio = _audio(tmp_path)
    words = [FakeWord(float(i), float(i + 1), f"w{i}") for i in range(12)]
    transcriber = FakeTranscriber([FakeSegment(0.0, 12.0, " ".join(w.word for w in words), words)])

    lines, _, _ = transcribe_lyrics(audio, model_dir=tmp_path, transcriber=transcriber)

    assert len(lines) > 1
    assert all(line.end - line.start <= 8.05 for line in lines)
    assert " ".join(line.text for line in lines).split() == [word.word for word in words]


def test_language_passthrough(tmp_path):
    audio = _audio(tmp_path)
    transcriber = FakeTranscriber(
        [FakeSegment(0.0, 1.0, "test", [FakeWord(0.0, 1.0, "test")])],
        FakeInfo(language="ja", duration=1.0),
    )

    lines, language, _ = transcribe_lyrics(
        audio,
        model_dir=tmp_path,
        language="ja",
        transcriber=transcriber,
    )

    assert lines
    assert language == "ja"
    assert transcriber.kwargs["language"] == "ja"


def test_lazy_segment_error_keeps_partial_lines(tmp_path):
    class ExplodingTranscriber:
        def transcribe(self, path: str, **kwargs):
            def segments():
                yield FakeSegment(0.0, 1.0, "hello", [FakeWord(0.0, 1.0, "hello")])
                raise RuntimeError("decode boom")

            return segments(), FakeInfo(language="en", duration=10.0)

    lines, language, warnings = transcribe_lyrics(
        _audio(tmp_path),
        model_dir=tmp_path,
        transcriber=ExplodingTranscriber(),
    )

    assert [line.text for line in lines] == ["hello"]
    assert language == "en"
    assert any("stopped early" in warning for warning in warnings)
    assert "decode boom" in " ".join(warnings)


def test_missing_model_returns_warning(tmp_path):
    audio = _audio(tmp_path)

    lines, language, warnings = transcribe_lyrics(audio, model_dir=tmp_path / "missing")

    assert lines == []
    assert language is None
    assert any("model" in warning.lower() for warning in warnings)


def test_no_speech_returns_warning(tmp_path):
    audio = _audio(tmp_path)
    transcriber = FakeTranscriber([], FakeInfo(language=None, duration=10.0))

    lines, language, warnings = transcribe_lyrics(audio, model_dir=tmp_path, transcriber=transcriber)

    assert lines == []
    assert language is None
    assert any("no lyrics" in warning.lower() for warning in warnings)


def test_lyrics_available_false_for_missing_dir(tmp_path):
    assert lyrics_available(tmp_path / "missing") is False


def test_lyrics_available_true_for_complete_dir(tmp_path, monkeypatch):
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt"):
        (tmp_path / name).write_bytes(b"x")
    monkeypatch.setattr("audio_to_tab.lyrics._faster_whisper_available", lambda: True)

    assert lyrics_available(tmp_path) is True


def test_default_model_dir_honours_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("ATT_LYRICS_MODEL_DIR", str(tmp_path))
    assert default_model_dir() == tmp_path


def test_model_manifest_is_pinned():
    assert set(MODEL_FILES) == {"model.bin", "config.json", "tokenizer.json", "vocabulary.txt"}
    for name, (sha256, size) in MODEL_FILES.items():
        assert len(sha256) == 64
        assert int(sha256, 16) >= 0
        assert size > 0
        assert name


def test_ensure_lyrics_model_returns_existing_complete_dir(tmp_path, monkeypatch):
    for name, (_sha256, size) in MODEL_FILES.items():
        (tmp_path / name).write_bytes(b"x" * min(size, 4))

    # A fake hash cannot match; the function must still report a verifiable path only after
    # the real download. We only assert the directory is returned for a complete-by-name cache.
    monkeypatch.setattr("audio_to_tab.lyrics.file_sha256", lambda path: MODEL_FILES[Path(path).name][0])
    monkeypatch.setattr("audio_to_tab.lyrics.download_sha256_file", lambda *args, **kwargs: args[1])

    assert ensure_lyrics_model(tmp_path) == tmp_path
