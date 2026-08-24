"""Subprocess helpers for desktop and CLI paths."""

from __future__ import annotations

import subprocess
import sys


def subprocess_run_kwargs() -> dict:
    """Extra kwargs for ``subprocess.run`` / ``Popen`` on Windows.

    ffmpeg and ffprobe are console executables; without ``CREATE_NO_WINDOW`` a
    frozen ``console=False`` app briefly flashes a terminal on every call.
    """
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if flags:
            return {"creationflags": flags}
    return {}
