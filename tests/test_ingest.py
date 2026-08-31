"""Unit tests for YouTube ingest (no network unless RUN_YOUTUBE_INTEGRATION=1)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from audio_to_tab.ingest import (
    YouTubeDownloadError,
    YouTubeSearchError,
    _is_403_error,
    _resolve_downloaded_wav,
    _thumbnail_url_for_entry,
    _watch_url_from_entry,
    _youtube_log_path,
    _youtube_ydl_opts,
    download_youtube_audio,
    format_youtube_duration,
    is_youtube_url,
    normalize_audio,
    search_youtube_videos,
    temporary_output_path,
)


def test_youtube_url_allowlist():
    assert is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert is_youtube_url("https://youtu.be/abc")
    assert not is_youtube_url("https://example.com/watch?v=abc")
    assert not is_youtube_url("https://youtube.com.evil.test/watch")
    assert not is_youtube_url("file:///tmp/x")


def test_download_youtube_rejects_non_youtube(tmp_path):
    with pytest.raises(ValueError, match="Only YouTube"):
        download_youtube_audio("https://example.com/a.wav", tmp_path)


def test_youtube_ydl_opts_sets_noplaylist_and_client():
    opts = _youtube_ydl_opts(template="/tmp/%(title)s.%(ext)s", player_client="default,-android_sdkless")
    assert opts["noplaylist"] is True
    assert opts["retries"] == 3
    assert opts["extractor_args"]["youtube"]["player_client"] == ["default", "-android_sdkless"]
    assert opts["postprocessors"][0]["preferredcodec"] == "wav"
    assert "logger" not in opts


def test_youtube_ydl_opts_forwards_file_logger_to_ytdlp(tmp_path):
    log = tmp_path / "yt-dlp.log"
    opts = _youtube_ydl_opts(
        template="/tmp/%(title)s.%(ext)s",
        player_client="default",
        verbose=True,
        log_path=log,
    )
    logger = opts.get("logger")
    assert logger is not None
    logger.debug("hello from yt-dlp")
    assert "hello from yt-dlp" in log.read_text(encoding="utf-8")


def test_youtube_log_path_is_platform_neutral(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIO_TOOLS_DEBUG", "1")
    monkeypatch.setenv("AUDIO_TOOLS_LOG_DIR", "")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr("audio_to_tab.ingest.sys.platform", "win32")
    path = _youtube_log_path()
    assert path is not None
    assert path.parent.is_dir()
    assert path.name == "yt-dlp.log"
    assert str(path).startswith(str(tmp_path))
    monkeypatch.setattr("audio_to_tab.ingest.sys.platform", "linux")
    linux_path = _youtube_log_path()
    assert linux_path is not None
    assert "audiotools" in linux_path.parts


def test_is_403_error():
    assert _is_403_error(Exception("ERROR: unable to download video data: HTTP Error 403: Forbidden"))
    assert not _is_403_error(Exception("Video unavailable"))


def test_format_youtube_duration():
    assert format_youtube_duration(65) == "1:05"
    assert format_youtube_duration(3661) == "1:01:01"
    assert format_youtube_duration(None) == ""
    assert format_youtube_duration(-1) == ""


def test_watch_url_from_flat_search_entry():
    assert (
        _watch_url_from_entry({"id": "BaW_jenozKc", "title": "clip"})
        == "https://www.youtube.com/watch?v=BaW_jenozKc"
    )
    assert _watch_url_from_entry({"url": "https://youtu.be/abc123XYZ_-"}) == "https://youtu.be/abc123XYZ_-"
    assert _watch_url_from_entry({"title": "no id"}) is None


def test_thumbnail_url_prefers_entry_then_cdn_fallback():
    assert (
        _thumbnail_url_for_entry(
            {"thumbnail": "https://img.example/custom.jpg"},
            "vid1",
        )
        == "https://img.example/custom.jpg"
    )
    assert (
        _thumbnail_url_for_entry(
            {"thumbnails": [{"url": "https://img.example/lo.jpg"}, {"url": "https://img.example/hi.jpg"}]},
            "vid1",
        )
        == "https://img.example/hi.jpg"
    )
    assert _thumbnail_url_for_entry({}, "vid1").endswith("/hqdefault.jpg")
    assert "vid1" in _thumbnail_url_for_entry({}, "vid1")


def test_search_youtube_videos_uses_ytsearch_and_maps_hits():
    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, query, download=False):
            assert download is False
            assert query.startswith("ytsearch5:")
            assert "megadeth" in query.lower()
            return {
                "entries": [
                    {
                        "id": "vid1",
                        "title": "Song A",
                        "channel": "Artist",
                        "duration": 201,
                        "thumbnail": "https://img.example/a.jpg",
                    },
                    {
                        "id": "vid2",
                        "title": "Song B",
                        "uploader": "Other",
                        "duration": None,
                    },
                    None,
                    {"title": "missing id"},
                ]
            }

    with patch("yt_dlp.YoutubeDL", FakeYDL):
        hits = search_youtube_videos("Megadeth Hangar 18", max_results=5)
    assert len(hits) == 2
    assert hits[0].url == "https://www.youtube.com/watch?v=vid1"
    assert hits[0].title == "Song A"
    assert hits[0].channel == "Artist"
    assert hits[0].duration_sec == 201
    assert hits[0].thumbnail_url == "https://img.example/a.jpg"
    assert hits[1].channel == "Other"
    assert hits[1].duration_sec is None
    assert hits[1].thumbnail_url.endswith("/hqdefault.jpg")


def test_search_youtube_videos_rejects_blank_query():
    with pytest.raises(ValueError, match="search query"):
        search_youtube_videos("   ")


def test_search_youtube_videos_wraps_backend_errors():
    class Boom:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, query, download=False):
            raise RuntimeError("network down")

    with patch("yt_dlp.YoutubeDL", Boom):
        with pytest.raises(YouTubeSearchError, match="Could not search YouTube"):
            search_youtube_videos("anything")


def test_download_does_not_require_js_runtime(tmp_path, monkeypatch):
    """End users must not install Deno/Node to paste a public YouTube URL."""
    monkeypatch.setattr("audio_to_tab.ingest.shutil.which", lambda _name: None)
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF")
    normalized: list[Path] = []

    def fake_normalize(path, *_args, **_kwargs):
        normalized.append(Path(path))
        return Path(path)

    monkeypatch.setattr("audio_to_tab.ingest.normalize_audio", fake_normalize)

    class FakeYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=True):
            return {"title": "clip"}

    with patch("yt_dlp.YoutubeDL", FakeYDL):
        path = download_youtube_audio("https://www.youtube.com/watch?v=abc", tmp_path)
    assert path == wav
    assert normalized == [wav]


def test_download_retries_after_403_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr("audio_to_tab.ingest._clear_ytdlp_cache", lambda: None)

    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF")
    monkeypatch.setattr("audio_to_tab.ingest.normalize_audio", lambda p, *_a, **_k: Path(p))
    calls: list[str] = []

    class FakeYDL:
        def __init__(self, opts):
            self.client = ",".join(opts["extractor_args"]["youtube"]["player_client"])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=True):
            calls.append(self.client)
            if len(calls) == 1:
                raise Exception("ERROR: unable to download video data: HTTP Error 403: Forbidden")
            return {"title": "clip"}

    with patch("yt_dlp.YoutubeDL", FakeYDL):
        path = download_youtube_audio("https://www.youtube.com/watch?v=abc", tmp_path)
    assert path == wav
    assert len(calls) == 2
    assert "android_sdkless" in calls[0]
    assert "web_safari" in calls[1]


def test_download_403_twice_raises_user_error(tmp_path, monkeypatch):
    monkeypatch.setattr("audio_to_tab.ingest._clear_ytdlp_cache", lambda: None)

    class Always403:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=True):
            raise Exception("ERROR: unable to download video data: HTTP Error 403: Forbidden")

    with patch("yt_dlp.YoutubeDL", Always403):
        with pytest.raises(YouTubeDownloadError, match="Upload the audio file") as caught:
            download_youtube_audio("https://youtu.be/abc", tmp_path)
    assert "HTTP 403" in str(caught.value)
    assert "brew install deno" not in str(caught.value).lower()


@pytest.mark.youtube
def test_youtube_public_download_integration(tmp_path):
    """Hits the public internet. Skip unless RUN_YOUTUBE_INTEGRATION=1."""
    if os.environ.get("RUN_YOUTUBE_INTEGRATION") != "1":
        pytest.skip("Set RUN_YOUTUBE_INTEGRATION=1 to run live YouTube download")
    # Short public test clip used by yt-dlp docs / CC samples.
    url = "https://www.youtube.com/watch?v=BaW_jenozKc"
    path = download_youtube_audio(url, tmp_path)
    assert path.is_file()


def test_resolve_downloaded_wav_prefers_title_match_over_stale(tmp_path, monkeypatch):
    stale = tmp_path / "Old Song.wav"
    stale.write_bytes(b"s")
    target = tmp_path / "My Song (Official Audio).wav"
    target.write_bytes(b"t")
    seen: list[Path] = []
    outs: list[Path] = []

    def fake_norm(p, *_a, **k):
        seen.append(Path(p))
        out = Path(k.get("output_path") or p)
        outs.append(out)
        out.write_bytes(b"norm")
        return out

    monkeypatch.setattr("audio_to_tab.ingest.normalize_audio", fake_norm)

    got = _resolve_downloaded_wav(tmp_path, "My Song (Official Audio)", "https://x/1")
    assert got == target
    assert seen == [target]
    # In-place: normalized into a same-dir temp, then moved onto the title file.
    assert len(outs) == 1
    assert outs[0] != target and outs[0].parent == tmp_path
    assert target.read_bytes() == b"norm"
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]


def test_resolve_downloaded_wav_no_title_match_uses_newest_normalized(tmp_path, monkeypatch):
    import os
    import time as _time

    a = tmp_path / "a.wav"
    a.write_bytes(b"a")
    b = tmp_path / "zzz.wav"
    b.write_bytes(b"b")
    now = _time.time() - 10
    os.utime(a, (now, now))
    os.utime(b, (now + 30, now + 30))
    seen: list[Path] = []
    monkeypatch.setattr(
        "audio_to_tab.ingest.normalize_audio",
        lambda p, *_a, **_k: (seen.append(Path(p)), Path(p))[1],
    )

    got = _resolve_downloaded_wav(tmp_path, "Totally Different Title", "https://x/1")
    assert got == b
    assert seen == [b]


def test_resolve_downloaded_wav_no_candidates_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "audio_to_tab.ingest.normalize_audio",
        lambda p, *_a, **_k: Path(p),
    )
    with pytest.raises(FileNotFoundError, match="not found"):
        _resolve_downloaded_wav(tmp_path, "clip", "https://x/1")


def test_temporary_output_path_closes_fd_and_creates_file(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    out = temporary_output_path("audio_norm_", ".wav")
    assert out.exists()
    assert out.name.startswith("audio_norm_")
    # The leaked on-disk FD from mkstemp is closed, so the file is deletable
    # immediately on Windows (PermissionError otherwise).
    out.unlink()
    assert not out.exists()


def test_normalize_audio_deletes_temp_on_failure(tmp_path, monkeypatch):
    import tempfile
    from unittest.mock import MagicMock

    src = tmp_path / "in.wav"
    src.write_bytes(b"x")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(work))

    def boom(cmd, **kwargs):
        return MagicMock(returncode=1, stderr="corrupt input")

    with (
        patch("audio_to_tab.ingest._require_ffmpeg", return_value="ffmpeg"),
        patch("audio_to_tab.ingest.subprocess.run", side_effect=boom),
    ):
        with pytest.raises(RuntimeError, match="ffmpeg failed"):
            normalize_audio(src)
    assert not list(work.glob("audio_norm_*"))


def test_normalize_audio_temp_output_is_caller_owned(tmp_path, monkeypatch):
    import tempfile
    from unittest.mock import MagicMock

    src = tmp_path / "in.wav"
    src.write_bytes(b"x")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(work))

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"norm-wav")
        return MagicMock(returncode=0)

    with (
        patch("audio_to_tab.ingest._require_ffmpeg", return_value="ffmpeg"),
        patch("audio_to_tab.ingest.subprocess.run", side_effect=fake_run),
    ):
        out = normalize_audio(src)
    assert out.exists()
    # Caller owns the temp output; it is not removed out from under it but is
    # by no longer held by the engine's mkstemp FD.
    assert list(work.glob("audio_norm_*")) == [out]
    out.unlink()
