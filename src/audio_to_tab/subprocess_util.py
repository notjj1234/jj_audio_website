"""Subprocess helpers for desktop and CLI paths."""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import suppress


class JobAborted(Exception):
    """Raised when isolation should stop between pipeline stages (stop/pause)."""


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


def _stop_process(proc: subprocess.Popen, *, kill: bool = False) -> None:
    try:
        proc.terminate()
    except OSError:
        return
    if kill:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        with suppress(OSError):
            proc.kill()
        proc.wait()


def run_process(
    command: list[str],
    *,
    should_abort: Callable[[], bool] | None = None,
    timeout_sec: float | None = None,
    poll_interval: float = 0.5,
    **kwargs,
):
    """Run ``command`` with a Popen handle the abort path can terminate.

    Polls on ``communicate(timeout=...)`` so a ``should_abort()`` callback is
    honored mid-run (the child is terminated before ``JobAborted`` is raised)
    and an optional ``timeout_sec`` cap kills a hung child. Returns a
    ``subprocess.CompletedProcess`` like ``subprocess.run`` (accepts the same
    ``capture_output`` / ``text`` / ``creationflags`` kwargs).
    """
    if kwargs.pop("capture_output", False):
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
    proc = subprocess.Popen(command, **kwargs)
    started = time.monotonic()
    try:
        while True:
            if should_abort is not None and should_abort():
                raise JobAborted("Job aborted")
            if timeout_sec is not None and time.monotonic() - started > timeout_sec:
                raise subprocess.TimeoutExpired(cmd=command, timeout=timeout_sec)
            try:
                stdout, stderr = proc.communicate(timeout=poll_interval)
                return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                continue
    except subprocess.TimeoutExpired:
        _stop_process(proc)
        raise
    except BaseException:
        if proc.poll() is None:
            _stop_process(proc)
        raise
