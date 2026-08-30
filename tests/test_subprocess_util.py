"""Tests for subprocess helpers."""

from __future__ import annotations

import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from audio_to_tab.subprocess_util import (
    JobAborted,
    run_process,
    subprocess_run_kwargs,
)


def test_subprocess_run_kwargs_empty_off_windows():
    with patch.object(sys, "platform", "darwin"):
        assert subprocess_run_kwargs() == {}


def test_subprocess_run_kwargs_create_no_window_on_windows():
    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if not flag:
        return
    with patch.object(sys, "platform", "win32"):
        assert subprocess_run_kwargs() == {"creationflags": flag}


def _sleeper() -> list[str]:
    return [sys.executable, "-c", "import time; time.sleep(60)"]


def test_run_process_returns_completed_process():
    result = run_process(
        [sys.executable, "-c", "import sys; sys.exit(3)"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3


def test_run_process_success_reads_stdout():
    result = run_process(
        [sys.executable, "-c", "print('hi')"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "hi"


def test_run_process_abort_terminates_inflight_child():
    started = time.monotonic()
    polls = {"n": 0}

    def should_abort() -> bool:
        polls["n"] += 1
        return polls["n"] >= 2

    with pytest.raises(JobAborted):
        run_process(
            _sleeper(),
            should_abort=should_abort,
            poll_interval=0.1,
            capture_output=True,
        )
    assert time.monotonic() - started < 30


def test_run_process_timeout_kills_hung_child():
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        run_process(
            _sleeper(),
            timeout_sec=0.2,
            poll_interval=0.1,
            capture_output=True,
        )
    assert time.monotonic() - started < 30


def test_job_aborted_reexported_from_isolate():
    from audio_to_tab.isolate import JobAborted as IsolateJobAborted

    assert IsolateJobAborted is JobAborted