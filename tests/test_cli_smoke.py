"""Smoke tests for the five CLI entrypoints (wiring + help, not full runs).

Each CLI module's ``main()`` builds an argparse parser and exits 0 on ``--help``
without touching the network or heavy models. These tests only exercise that
wiring plus the ``[project.scripts]`` registration in pyproject.toml.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

CLI_MODULES = ("isolate", "pipeline", "transcribe", "tab2pdf", "mid2tab")
EXPECTED_SCRIPTS = {
    "isolate": "audio-isolate",
    "pipeline": "audio-pipeline",
    "transcribe": "audio-transcribe",
    "tab2pdf": "audio-tab2pdf",
    "mid2tab": "audio-mid2tab",
}

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - py3.10
    tomllib = None


@pytest.mark.parametrize("module", CLI_MODULES)
def test_cli_help_exits_zero(module: str) -> None:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", f"audio_to_tab.cli.{module}", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "usage" in proc.stdout.lower()


def test_pyproject_registers_all_entrypoints() -> None:
    if tomllib is None:
        pytest.skip("tomllib requires Python 3.11+")
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    expected = {name: f"audio_to_tab.cli.{m}:main" for m, name in EXPECTED_SCRIPTS.items()}
    assert pyproject["project"]["scripts"] == expected