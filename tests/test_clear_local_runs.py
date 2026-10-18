"""Desktop local run clearing (compliance C20)."""

from __future__ import annotations

from pathlib import Path

import ui.common as common


def test_clear_all_local_runs(tmp_path: Path, monkeypatch):
    data = tmp_path / "ui_runs"
    data.mkdir()
    (data / "run-a").mkdir()
    (data / "run-a" / "meta.json").write_text("{}", encoding="utf-8")
    (data / "run-b").mkdir()
    (data / "stray.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(common, "DATA_DIR", data)

    deleted, failed = common.clear_all_local_runs()
    assert failed == 0
    assert deleted == 2
    assert not (data / "run-a").exists()
    assert not (data / "run-b").exists()
    assert (data / "stray.txt").exists()
