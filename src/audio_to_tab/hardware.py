"""Host RAM / GPU probe and desktop Audio Isolation recommendations.

Frozen desktop ships this module (not ``backend/``). Hosted Auto still uses
``backend.capabilities``, which re-exports the same probe types so policy
does not drift.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from audio_to_tab.edition import EDITION_CUDA, desktop_edition

LOW_RAM_GB = 8.0
# Torch MPS needs working room for the ~700 MB fp32 BS-RoFormer-SW weights plus
# activations; 8 GB unified-memory Macs (mostly base M1/M2/M3/M4) stay on CPU.
MPS_MIN_RAM_GB = 12.0

NVIDIA_ONLY_DISCLAIMER = (
    "GPU acceleration is NVIDIA CUDA only — not AMD, Intel, or Apple GPUs. "
    "Requires an NVIDIA graphics card and current drivers."
)

MAC_ACCEL_NOTE = (
    "NVIDIA CUDA is not available on Mac. Apple Silicon can use its own GPU "
    "via the Apple GPU (MPS) device when the ≥12 GB RAM gate is met."
)

CUDA_UNAVAILABLE_MESSAGE = (
    "NVIDIA CUDA is not available on this computer. "
    "Isolation will not start on GPU. Choose CPU, or install current NVIDIA drivers "
    "on a machine with an NVIDIA graphics card."
)

# Cached after the first torch import — probing is expensive.
_cached_probe: HostProbe | None = None


@dataclass(frozen=True)
class HostProbe:
    cuda: bool
    mps: bool
    ram_gb: float | None
    single_flight: bool = False


def probe_torch() -> tuple[bool, bool]:
    """Return (cuda_available, mps_available). Missing torch → (False, False)."""
    try:
        import torch
    except ImportError:
        return False, False

    cuda = bool(torch.cuda.is_available())
    mps = False
    backend = getattr(torch.backends, "mps", None)
    if backend is not None:
        is_built = getattr(backend, "is_built", None)
        is_available = getattr(backend, "is_available", None)
        mps = bool(
            callable(is_built)
            and callable(is_available)
            and is_built()
            and is_available()
        )
    return cuda, mps


def probe_ram_gb() -> float | None:
    """Approximate physical RAM in GiB. None if the host cannot be measured."""
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        if page > 0 and pages > 0:
            return round((page * pages) / (1024**3), 1)
    except (ValueError, OSError, AttributeError):
        pass

    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            return round(int(out) / (1024**3), 1)
        except (OSError, ValueError, subprocess.SubprocessError):
            pass

    if sys.platform == "win32":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return round(stat.ullTotalPhys / (1024**3), 1)
        except (OSError, AttributeError, ValueError):
            pass

    return None


def reset_desktop_probe_cache() -> None:
    """Clear the cached probe (tests)."""
    global _cached_probe
    _cached_probe = None


def _physical_perf_cores() -> int | None:
    """P-core count on Apple Silicon (macOS arm64), else None.

    PyTorch defaults CPU inference to all logical threads, which mixes the
    efficient cores in on M1–M4; capping to performance cores keeps the big
    RoFormer transforms off the small cores.
    """
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "hw.perflevel0.physicalcpu"], text=True
        ).strip()
        n = int(out)
        return n if n > 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def recommended_cpu_threads(*, ram_gb: float | None = None) -> int:
    """PyTorch intra-op thread cap for CPU model inference.

    Apple Silicon: performance-core count (so M1 base → 4, M2 Pro → 8, M4 Max
    → 12+), clamped by RAM (8 GB → 4 threads, 16 GB → 8, 32 GB+ → all P-cores)
    so low-memory Macs keep working-room. Other hosts fall back to the logical
    CPU count.
    """
    total = os.cpu_count() or 1
    perf = _physical_perf_cores()
    base = perf if perf and perf > 0 else total
    rss = ram_gb if ram_gb is not None else probe_ram_gb()
    if rss is not None and rss > 0:
        base = min(base, max(2, int(rss // 2)))
    return max(1, base)


def resolve_safe_device(device: str, probe: HostProbe | None = None) -> str:
    """Never let a job run on an accelerator this host cannot use.

    CUDA keeps its hard failure (an NVIDIA build must not silently run on CPU);
    an MPS request on an ineligible Mac (no torch-MPS, or < 12 GB RAM) downgrades
    to CPU instead of failing the job.
    """
    if device == "cuda":
        ensure_cuda_available(device, probe)
        return "cuda"
    if device == "mps":
        if probe is None:
            _cuda, mps = probe_torch()
            ram = probe_ram_gb()
        else:
            mps, ram = probe.mps, probe.ram_gb
        ok = mps and (ram is None or ram >= MPS_MIN_RAM_GB)
        return "mps" if ok else "cpu"
    return device


def get_desktop_probe(*, force: bool = False) -> HostProbe:
    """Probe once per process; torch import is expensive."""
    global _cached_probe
    if force or _cached_probe is None:
        cuda, mps = probe_torch()
        _cached_probe = HostProbe(cuda=cuda, mps=mps, ram_gb=probe_ram_gb())
    return _cached_probe


def get_desktop_probe_without_torch() -> HostProbe:
    """RAM-only probe for first UI paint. Does not import torch."""
    cuda_ui = _cuda_edition_windows(platform=None)
    return HostProbe(cuda=cuda_ui, mps=False, ram_gb=probe_ram_gb())


def _platform(platform: str | None) -> str:
    return platform if platform is not None else sys.platform


def _cuda_edition_windows(*, platform: str | None) -> bool:
    """True on the NVIDIA desktop build (Windows). UI defaults to CUDA-only."""
    return _platform(platform).startswith("win") and desktop_edition() == EDITION_CUDA


def desktop_device_options(probe: HostProbe, *, platform: str | None = None) -> list[str]:
    """Devices the desktop UI may offer. Mac never lists CUDA; Apple Silicon with
    enough RAM also lists Apple GPU (MPS)."""
    if _cuda_edition_windows(platform=platform):
        return ["cuda"]
    options = ["cpu"]
    plat = _platform(platform)
    if plat.startswith("win") and probe.cuda:
        options.append("cuda")
    if (
        plat.startswith("darwin")
        and probe.mps
        and (probe.ram_gb is None or probe.ram_gb >= MPS_MIN_RAM_GB)
    ):
        options.append("mps")
    return options


def is_low_ram(probe: HostProbe) -> bool:
    return probe.ram_gb is not None and probe.ram_gb < LOW_RAM_GB


def desktop_recommend(probe: HostProbe, *, platform: str | None = None) -> dict[str, Any]:
    """Auto speed/quality/device for the Streamlit desktop app.

    Aligns with hosted Auto: low RAM → Faster/CPU; Windows CUDA → Balanced/cuda;
    Apple GPU (MPS) → Balanced/mps on capable Macs; otherwise Faster/CPU.
    Never recommends extreme or High-GPU.
    """
    if _cuda_edition_windows(platform=platform):
        if is_low_ram(probe):
            return {
                "speed": "faster",
                "quality": "fast",
                "device": "cuda",
                "notes": "Recommended: Faster on NVIDIA GPU. Use a short clip (≤90 s).",
            }
        return {
            "speed": "balanced",
            "quality": "balanced",
            "device": "cuda",
            "notes": "Recommended: Balanced on NVIDIA GPU.",
        }
    options = desktop_device_options(probe, platform=platform)
    if is_low_ram(probe):
        return {
            "speed": "faster",
            "quality": "fast",
            "device": "cpu",
            "notes": "Recommended: Faster on CPU. Use a short clip (≤90 s).",
        }
    gpu_dev = "cuda" if "cuda" in options else ("mps" if "mps" in options else "cpu")
    if gpu_dev == "mps":
        return {
            "speed": "balanced",
            "quality": "balanced",
            "device": "mps",
            "notes": "Recommended: Balanced on Apple GPU (MPS).",
        }
    if gpu_dev == "cuda":
        return {
            "speed": "balanced",
            "quality": "balanced",
            "device": "cuda",
            "notes": "Recommended: Balanced on NVIDIA GPU.",
        }
    return {
        "speed": "faster",
        "quality": "fast",
        "device": "cpu",
        "notes": "Recommended: Faster on CPU.",
    }


def resolve_desktop_speed(
    speed_id: str,
    probe: HostProbe,
    *,
    platform: str | None = None,
) -> dict[str, Any]:
    """Map a desktop speed radio id to quality + device for this host."""
    options = desktop_device_options(probe, platform=platform)
    gpu = "cuda" if "cuda" in options else ("mps" if "mps" in options else "cpu")

    if speed_id not in ("faster", "balanced", "best"):
        return {
            "id": "balanced",
            "label": "Balanced",
            "quality": "balanced",
            "device": gpu,
            "help": "",
        }

    if speed_id == "faster":
        device = gpu if _cuda_edition_windows(platform=platform) else "cpu"
        return {
            "id": "faster",
            "label": "Faster",
            "quality": "fast",
            "device": device,
            "help": "",
        }
    if speed_id == "balanced":
        return {
            "id": "balanced",
            "label": "Balanced",
            "quality": "balanced",
            "device": gpu,
            "help": "",
        }
    return {
        "id": "best",
        "label": "Best",
        "quality": "high",
        "device": gpu,
        "help": "",
    }


def desktop_system_summary(probe: HostProbe, *, platform: str | None = None) -> str:
    ram = f"~{probe.ram_gb:g} GB RAM" if probe.ram_gb is not None else "RAM unknown"
    if _cuda_edition_windows(platform=platform):
        return f"This PC: {ram} · NVIDIA GPU"
    options = desktop_device_options(probe, platform=platform)
    accel = (
        "Apple GPU (MPS)"
        if "mps" in options
        else ("NVIDIA GPU" if "cuda" in options else "CPU")
    )
    return f"This PC: {ram} · {accel}"


def desktop_recommend_caption(probe: HostProbe, *, platform: str | None = None) -> str:
    rec = desktop_recommend(probe, platform=platform)
    extra = MAC_ACCEL_NOTE if _platform(platform).startswith("darwin") else NVIDIA_ONLY_DISCLAIMER
    return f"{rec['notes']} {extra}"


def ensure_cuda_available(device: str, probe: HostProbe | None = None) -> None:
    """Raise if the job asked for CUDA but torch cannot use it."""
    if device != "cuda":
        return
    host = probe
    if host is None:
        cuda, _mps = probe_torch()
        if not cuda:
            raise RuntimeError(CUDA_UNAVAILABLE_MESSAGE)
        return
    if not host.cuda:
        raise RuntimeError(CUDA_UNAVAILABLE_MESSAGE)


def separate_progress_message(device: str) -> str:
    if device == "cuda":
        return "Separating tracks — this can take a while on NVIDIA GPU"
    if device == "mps":
        return "Separating tracks — running on Apple GPU (Metal)"
    return "Separating tracks — this can take a while on CPU"
