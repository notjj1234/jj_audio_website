"""Global single-flight job gate for memory-constrained hosts (Oracle lite)."""

from __future__ import annotations

import threading

from fastapi import HTTPException

_lock = threading.Lock()
_busy = False


def try_acquire() -> bool:
    global _busy
    with _lock:
        if _busy:
            return False
        _busy = True
        return True


def release() -> None:
    global _busy
    with _lock:
        _busy = False


def is_busy() -> bool:
    with _lock:
        return _busy


def acquire_or_503(*, enabled: bool) -> None:
    if not enabled:
        return
    if not try_acquire():
        raise HTTPException(
            503,
            "Another job is already running on this host. Try again when it finishes "
            "(lite/Oracle profile allows one job at a time).",
        )
