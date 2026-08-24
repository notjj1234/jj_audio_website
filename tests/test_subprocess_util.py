"""Tests for subprocess helpers."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import patch

from audio_to_tab.subprocess_util import subprocess_run_kwargs


def test_subprocess_run_kwargs_empty_off_windows():
    with patch.object(sys, "platform", "darwin"):
        assert subprocess_run_kwargs() == {}


def test_subprocess_run_kwargs_create_no_window_on_windows():
    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if not flag:
        return
    with patch.object(sys, "platform", "win32"):
        assert subprocess_run_kwargs() == {"creationflags": flag}
