"""Unit tests for YouTube ingest (no network unless RUN_YOUTUBE_INTEGRATION=1)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from audio_to_tab.ingest import (
    YouTubeDownloadError,
    _is_403_error,
    _youtube_ydl_opts,
    download_youtube_audio,
    is_youtube_url,
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


def test_is_403_error():
    assert _is_403_error(Exception("ERROR: unable to download video data: HTTP Error 403: Forbidden"))
    assert not _is_403_error(Exception("Video unavailable"))


def test_download_does_not_require_js_runtime(tmp_path, monkeypatch):
    """End users must not install Deno/Node to paste a public YouTube URL."""
    monkeypatch.setattr("audio_to_tab.ingest.shutil.which", lambda _name: None)
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF")

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


def test_download_retries_after_403_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr("audio_to_tab.ingest._clear_ytdlp_cache", lambda: None)

    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF")
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
    assert path.suffix.lower() == ".wav"
    assert path.stat().st_size > 1000
