"""Tests for ui.common run listing / deletion helpers."""

from __future__ import annotations

from pathlib import Path

import ui.common as common


def test_delete_run_removes_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    run_dir = tmp_path / "abc-123"
    run_dir.mkdir()
    (run_dir / "meta.json").write_text("{}", encoding="utf-8")
    (run_dir / "vocals.wav").write_bytes(b"RIFF")

    assert common.delete_run(run_dir) is True
    assert not run_dir.exists()


def test_delete_run_rejects_paths_outside_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "ui_runs")
    (tmp_path / "ui_runs").mkdir()
    outside = tmp_path / "other"
    outside.mkdir()
    (outside / "file.txt").write_text("x", encoding="utf-8")

    assert common.delete_run(outside) is False
    assert outside.exists()


def test_delete_run_rejects_data_dir_itself(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    assert common.delete_run(tmp_path) is False
    assert tmp_path.exists()


def test_delete_run_rejects_nested_path(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    nested = tmp_path / "run" / "preview"
    nested.mkdir(parents=True)
    assert common.delete_run(nested) is False
    assert nested.exists()


def test_delete_run_already_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    missing = tmp_path / "gone"
    assert common.delete_run(missing) is True
