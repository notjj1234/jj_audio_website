"""Tests for ui.isolate_state helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ui.isolate_state import (
    format_elapsed,
    format_progress_label,
    should_hide_stale_results,
    stage_progress_percent,
    sync_output_name_on_upload,
    upload_fingerprint,
)


def test_upload_fingerprint():
    f = SimpleNamespace(name="song.mp3", size=12345)
    assert upload_fingerprint(f) == "song.mp3:12345"
    assert upload_fingerprint(None) is None


def test_sync_output_name_on_upload_new_file():
    f = SimpleNamespace(name="new_track.wav", size=999)
    fp, name, changed = sync_output_name_on_upload(
        f, last_fp="old.wav:1", output_name="old"
    )
    assert fp == "new_track.wav:999"
    assert name == "new_track"
    assert changed is True


def test_sync_output_name_on_upload_same_file():
    f = SimpleNamespace(name="same.wav", size=100)
    fp, name, changed = sync_output_name_on_upload(
        f, last_fp="same.wav:100", output_name="same"
    )
    assert fp == "same.wav:100"
    assert name == "same"
    assert changed is False


def test_should_hide_stale_results():
    assert not should_hide_stale_results(pending_upload_fp=None, has_artifacts=True)
    assert not should_hide_stale_results(pending_upload_fp="x:1", has_artifacts=False)
    assert should_hide_stale_results(pending_upload_fp="new.mp3:500", has_artifacts=True)


def test_stage_progress_percent_weighted():
    assert stage_progress_percent("ingest") == pytest.approx(0.05)
    assert stage_progress_percent("separate") == pytest.approx(0.80)
    assert stage_progress_percent("done") == pytest.approx(1.0)
    assert stage_progress_percent("unknown") == 0.0


def test_format_progress_label():
    assert format_progress_label(0.42, "Running Demucs") == "42% — Running Demucs"


def test_format_elapsed():
    assert format_elapsed(65) == "1:05"
    assert format_elapsed(0) == "0:00"
