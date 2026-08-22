#!/usr/bin/env python3
"""Phase 0 memory spike: peak RSS for htdemucs_6s quality=fast at 60/90/120s.

Writes docs/oracle-free-memory-spike.md with pass/fail vs Oracle Always Free 12 GB.
Run: PYTHONPATH=src:. .venv311/bin/python scripts/oracle_free_memory_spike.py
"""

from __future__ import annotations

import os
import resource
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "oracle-free-memory-spike.md"
DURATIONS = (60, 90, 120)
# Pass if peak under this (GiB); fail at or above 11 GiB
PASS_GIB = 10.0
FAIL_GIB = 11.0


def _rss_kib(pid: int) -> int:
    """Best-effort RSS in KiB for pid (macOS/Linux)."""
    try:
        out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)], text=True)
        return int(out.strip() or "0")
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return 0


def _tree_rss_kib(root_pid: int) -> int:
    total = _rss_kib(root_pid)
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,ppid=,rss="], text=True)
    except subprocess.CalledProcessError:
        return total
    children: dict[int, list[int]] = {}
    rss_map: dict[int, int] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            pid, ppid, rss = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        rss_map[pid] = rss
        children.setdefault(ppid, []).append(pid)

    stack = [root_pid]
    seen = {root_pid}
    while stack:
        pid = stack.pop()
        for c in children.get(pid, []):
            if c not in seen:
                seen.add(c)
                total += rss_map.get(c, 0)
                stack.append(c)
    return total


def _make_wav(path: Path, duration_sec: float, sr: int = 44100) -> None:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    # Stereo mix of a few tones so Demucs has content across bands
    mono = (
        0.2 * np.sin(2 * np.pi * 220 * t)
        + 0.15 * np.sin(2 * np.pi * 440 * t)
        + 0.1 * np.sin(2 * np.pi * 110 * t)
    ).astype(np.float32)
    stereo = np.stack([mono, mono], axis=1)
    sf.write(path, stereo, sr)


def run_one(duration_sec: int, work: Path) -> dict:
    wav = work / f"tone_{duration_sec}s.wav"
    out_dir = work / f"out_{duration_sec}s"
    out_dir.mkdir(parents=True, exist_ok=True)
    _make_wav(wav, float(duration_sec))

    cmd = [
        sys.executable,
        "-m",
        "demucs",
        "-n",
        "htdemucs_6s",
        "--shifts",
        "0",
        "--overlap",
        "0.25",
        "-d",
        "cpu",
        "-o",
        str(out_dir),
        str(wav),
    ]
    env = {**os.environ, "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
    peak = [0]
    stop = threading.Event()

    def poller(pid: int) -> None:
        while not stop.wait(0.5):
            peak[0] = max(peak[0], _tree_rss_kib(pid))

    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env)
    thr = threading.Thread(target=poller, args=(proc.pid,), daemon=True)
    thr.start()
    rc = proc.wait()
    stop.set()
    thr.join(timeout=2)
    # Final sample
    peak[0] = max(peak[0], _tree_rss_kib(proc.pid) if rc == 0 else peak[0])
    elapsed = time.perf_counter() - t0
    peak_gib = peak[0] / (1024 * 1024)
    return {
        "duration_sec": duration_sec,
        "exit_code": rc,
        "elapsed_sec": round(elapsed, 1),
        "peak_rss_kib": peak[0],
        "peak_rss_gib": round(peak_gib, 2),
        "ok": rc == 0,
    }


def main() -> int:
    import platform

    arch = platform.machine()
    try:
        import torch

        torch_ver = torch.__version__
        torch_ok = True
    except Exception as exc:
        torch_ver = str(exc)
        torch_ok = False

    try:
        import demucs  # noqa: F401

        demucs_ok = True
    except Exception:
        demucs_ok = False

    results: list[dict] = []
    if torch_ok and demucs_ok:
        with tempfile.TemporaryDirectory(prefix="oracle_spike_") as td:
            work = Path(td)
            for dur in DURATIONS:
                print(f"Running htdemucs_6s fast CPU for {dur}s…", flush=True)
                results.append(run_one(dur, work))
                print(
                    f"  peak={results[-1]['peak_rss_gib']} GiB "
                    f"elapsed={results[-1]['elapsed_sec']}s rc={results[-1]['exit_code']}",
                    flush=True,
                )

    max_peak = max((r["peak_rss_gib"] for r in results), default=0.0)
    any_fail = any(not r["ok"] for r in results) or not results
    if any_fail or max_peak >= FAIL_GIB:
        verdict = "FAIL"
        note = (
            "Oracle Always Free (12 GB) is not reliable for isolate at these lengths. "
            "Use a ~16–24 GB x86 VPS (Hetzner/Contabo)."
        )
    elif max_peak <= PASS_GIB:
        verdict = "PASS"
        note = (
            "Peak RSS stayed under ~10 GiB for measured clips. Short-clip lite profile "
            "on Oracle Free is plausible with single-flight jobs and swap."
        )
    else:
        verdict = "MARGINAL"
        note = (
            f"Peak {max_peak} GiB is between pass ({PASS_GIB}) and fail ({FAIL_GIB}) GiB. "
            "Oracle Free only with hard ≤60–90s caps, swap, and single-flight."
        )

    ru = resource.getrusage(resource.RUSAGE_SELF)
    lines = [
        "# Oracle Always Free — Demucs memory spike",
        "",
        f"- Date: {time.strftime('%Y-%m-%d')}",
        f"- Host arch: `{arch}`",
        f"- Python: `{sys.version.split()[0]}`",
        f"- Torch: `{torch_ver}` (ok={torch_ok})",
        f"- Demucs import ok: `{demucs_ok}`",
        f"- Model: `htdemucs_6s`, quality flags: shifts=0 overlap=0.25, device=cpu",
        f"- Verdict: **{verdict}**",
        "",
        note,
        "",
        "| Duration (s) | Peak RSS (GiB) | Elapsed (s) | Exit |",
        "|-------------:|---------------:|------------:|-----:|",
    ]
    for r in results:
        lines.append(
            f"| {r['duration_sec']} | {r['peak_rss_gib']} | {r['elapsed_sec']} | {r['exit_code']} |"
        )
    if not results:
        lines.append("| — | — | — | spike skipped |")
    lines.extend(
        [
            "",
            f"Pass criterion: peak &lt; {PASS_GIB} GiB. Fail: peak ≥ {FAIL_GIB} GiB or OOM/nonzero exit.",
            f"Parent process max RSS (self, KiB, informational): {getattr(ru, 'ru_maxrss', 'n/a')}",
            "",
        ]
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} verdict={verdict}", flush=True)
    return 0 if verdict != "FAIL" and results else 1


if __name__ == "__main__":
    raise SystemExit(main())
