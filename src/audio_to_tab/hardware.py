"""Host RAM / GPU probe and desktop Audio Isolation recommendations.

Frozen desktop ships this module (not ``backend/``). Hosted Auto still uses
``backend.capabilities``, which re-exports the same probe types so policy
does not drift.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from audio_to_tab.edition import (
    EDITION_BOTH,
    EDITION_CUDA,
    desktop_edition,
    edition_ships_cuda_torch,
)

LOW_RAM_GB = 8.0
# Torch MPS needs working room for the ~700 MB fp32 BS-RoFormer-SW weights plus
# activations; 8 GB unified-memory Macs (mostly base M1/M2/M3/M4) stay on CPU.
MPS_MIN_RAM_GB = 12.0
# Live headroom gates for Lite auto: prefer CPU when free/available RAM is low
# or swap is already heavy (unified-memory Macs thrash under DAW + tabs + MPS).
MEMORY_TIGHT_FREE_GB = 4.0
MEMORY_TIGHT_FREE_FRAC = 0.20
MEMORY_TIGHT_SWAP_GB = 2.0

NVIDIA_ONLY_DISCLAIMER = (
    "GPU acceleration is NVIDIA CUDA only (not AMD, Intel, or Apple GPUs). "
    "Needs an NVIDIA card and current drivers."
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
_CPU_BRAND_UNSET = object()
_cached_cpu_brand: str | None | object = _CPU_BRAND_UNSET


@dataclass(frozen=True)
class HostProbe:
    cuda: bool
    mps: bool
    ram_gb: float | None
    single_flight: bool = False
    cpu_brand: str | None = None


@dataclass(frozen=True)
class MemoryPressure:
    """Live memory headroom (not installed capacity).

    ``free_gb`` is approximate available/reclaimable physical RAM. ``swap_used_gb``
    is set on macOS when measurable; None means unknown (do not treat as tight).
    """

    free_gb: float | None
    total_gb: float | None = None
    swap_used_gb: float | None = None


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


def _darwin_swap_used_gb() -> float | None:
    """Parse ``sysctl vm.swapusage`` used field when present."""
    try:
        out = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True)
    except (OSError, subprocess.SubprocessError):
        return None
    # Example: "total = 1024.00M  used = 234.50M  free = 789.50M  ..."
    used_m: float | None = None
    tokens = out.replace("=", " ").split()
    for i, tok in enumerate(tokens):
        if tok.lower() != "used" or i + 1 >= len(tokens):
            continue
        raw = tokens[i + 1].upper().rstrip("B")
        try:
            if raw.endswith("G"):
                used_m = float(raw[:-1]) * 1024.0
            elif raw.endswith("M"):
                used_m = float(raw[:-1])
            elif raw.endswith("K"):
                used_m = float(raw[:-1]) / 1024.0
            else:
                used_m = float(raw) / (1024.0 * 1024.0)
        except ValueError:
            used_m = None
        break
    if used_m is None:
        return None
    return round(used_m / 1024.0, 2)


def _darwin_available_ram_gb() -> tuple[float | None, float | None]:
    """Return (available_gb, total_gb) from vm_stat + hw.memsize."""
    total = None
    try:
        out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
        total = int(out) / (1024**3)
    except (OSError, ValueError, subprocess.SubprocessError):
        total = None
    try:
        vm = subprocess.check_output(["vm_stat"], text=True)
    except (OSError, subprocess.SubprocessError):
        return None, total
    page_size = 4096
    counts: dict[str, int] = {}
    for line in vm.splitlines():
        lower = line.lower()
        if "page size of" in lower:
            bits = lower.replace(".", " ").split()
            for i, bit in enumerate(bits):
                if bit == "of" and i + 1 < len(bits):
                    with contextlib.suppress(ValueError):
                        page_size = int(bits[i + 1])
            continue
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        num = rest.strip().rstrip(".").replace(",", "")
        try:
            counts[key.strip().lower()] = int(num)
        except ValueError:
            continue
    # Approximate pressure-facing headroom: free + speculative + purgeable + inactive.
    pages = (
        counts.get("pages free", 0)
        + counts.get("pages speculative", 0)
        + counts.get("pages purgeable", 0)
        + counts.get("pages inactive", 0)
    )
    if pages <= 0:
        return None, total
    free_gb = (pages * page_size) / (1024**3)
    return round(free_gb, 2), (round(total, 1) if total is not None else None)


def _win_available_ram_gb() -> tuple[float | None, float | None]:
    """Return (avail_phys_gb, total_phys_gb) via GlobalMemoryStatusEx."""
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
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return None, None
        total = round(stat.ullTotalPhys / (1024**3), 1)
        free = round(stat.ullAvailPhys / (1024**3), 2)
        return free, total
    except (OSError, AttributeError, ValueError):
        return None, None


def probe_memory_pressure() -> MemoryPressure | None:
    """Live free/available RAM (+ macOS swap used). None if the host cannot be measured."""
    try:
        if sys.platform == "darwin":
            free_gb, total_gb = _darwin_available_ram_gb()
            if free_gb is None and total_gb is None:
                return None
            return MemoryPressure(
                free_gb=free_gb,
                total_gb=total_gb,
                swap_used_gb=_darwin_swap_used_gb(),
            )
        if sys.platform == "win32":
            free_gb, total_gb = _win_available_ram_gb()
            if free_gb is None and total_gb is None:
                return None
            return MemoryPressure(free_gb=free_gb, total_gb=total_gb, swap_used_gb=None)
        # Best-effort POSIX: MemAvailable from /proc/meminfo.
        total_kb = None
        avail_kb = None
        try:
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        avail_kb = int(line.split()[1])
        except (OSError, ValueError):
            return None
        if avail_kb is None and total_kb is None:
            return None
        return MemoryPressure(
            free_gb=round(avail_kb / (1024**2), 2) if avail_kb is not None else None,
            total_gb=round(total_kb / (1024**2), 1) if total_kb is not None else None,
        )
    except Exception:
        return None


def memory_pressure_is_tight(pressure: MemoryPressure | None) -> bool:
    """True when live headroom suggests preferring CPU over GPU for Lite auto.

    Unknown pressure (None / missing free) does **not** force CPU — fall back to
    installed-hardware recommend.
    """
    if pressure is None or pressure.free_gb is None:
        return False
    if pressure.free_gb < MEMORY_TIGHT_FREE_GB:
        return True
    if (
        pressure.total_gb is not None
        and pressure.total_gb > 0
        and (pressure.free_gb / pressure.total_gb) < MEMORY_TIGHT_FREE_FRAC
    ):
        return True
    return (
        pressure.swap_used_gb is not None
        and pressure.swap_used_gb >= MEMORY_TIGHT_SWAP_GB
    )


def probe_cpu_brand() -> str | None:
    """CPU brand string when the OS exposes one (macOS: ``Apple M2 Pro``)."""
    global _cached_cpu_brand
    if _cached_cpu_brand is not _CPU_BRAND_UNSET:
        return _cached_cpu_brand  # type: ignore[return-value]
    brand: str | None = None
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            ).strip()
            brand = out or None
        except (OSError, ValueError, subprocess.SubprocessError):
            brand = None
    _cached_cpu_brand = brand
    return brand


def apple_chip_label(brand: str | None) -> str | None:
    """Plain Apple Silicon name (``Apple M2 Pro``), or None for Intel/unknown."""
    if not brand:
        return None
    text = " ".join(str(brand).split())
    if text.lower().startswith("apple "):
        return text
    return None


def reset_desktop_probe_cache() -> None:
    """Clear the cached probe (tests)."""
    global _cached_probe, _cached_cpu_brand
    _cached_probe = None
    _cached_cpu_brand = _CPU_BRAND_UNSET


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


def cpu_thread_env(*, ram_gb: float | None = None) -> dict[str, str]:
    """Subprocess env so Demucs/OpenMP/MKL/PyTorch share the same thread cap."""
    n = str(recommended_cpu_threads(ram_gb=ram_gb))
    return {
        "OMP_NUM_THREADS": n,
        "MKL_NUM_THREADS": n,
        "TORCH_NUM_THREADS": n,
    }


def apply_recommended_cpu_threads(*, device: str | None = None) -> int | None:
    """Set ``torch.set_num_threads`` to ``recommended_cpu_threads()``.

    Skips non-CPU devices. Returns the cap applied, or None if skipped / unavailable.
    """
    if device is not None and device != "cpu":
        return None
    try:
        import torch
    except ImportError:
        return None
    n = recommended_cpu_threads()
    try:
        torch.set_num_threads(n)
    except Exception:
        return None
    return n


def roformer_max_audio_sec(probe: HostProbe | None = None) -> float:
    """Refuse RoFormer on audio longer than this (seconds).

    Known RAM under 12 GB → 90 s; unknown or ≥12 GB → 180 s.
    """
    ram = probe.ram_gb if probe is not None else probe_ram_gb()
    if ram is not None and ram < MPS_MIN_RAM_GB:
        return 90.0
    return 180.0


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
        _cached_probe = HostProbe(
            cuda=cuda,
            mps=mps,
            ram_gb=probe_ram_gb(),
            cpu_brand=probe_cpu_brand(),
        )
    return _cached_probe


def get_desktop_probe_without_torch() -> HostProbe:
    """RAM-only probe for first UI paint. Does not import torch."""
    cuda_ui = _ships_cuda_windows(platform=None)
    return HostProbe(
        cuda=cuda_ui,
        mps=False,
        ram_gb=probe_ram_gb(),
        cpu_brand=probe_cpu_brand(),
    )


def _platform(platform: str | None) -> str:
    return platform if platform is not None else sys.platform


def _ships_cuda_windows(*, platform: str | None) -> bool:
    """True when the Windows freeze ships CUDA PyTorch (cuda or both editions)."""
    return _platform(platform).startswith("win") and edition_ships_cuda_torch()


def _cuda_only_edition_windows(*, platform: str | None) -> bool:
    """True on the NVIDIA-only Windows freeze (no CPU device option in Pro)."""
    return (
        _platform(platform).startswith("win") and desktop_edition() == EDITION_CUDA
    )


def _both_edition_windows(*, platform: str | None) -> bool:
    return (
        _platform(platform).startswith("win") and desktop_edition() == EDITION_BOTH
    )


def desktop_device_options(probe: HostProbe, *, platform: str | None = None) -> list[str]:
    """Devices the desktop UI may offer. Mac never lists CUDA; Apple Silicon with
    enough RAM also lists Apple GPU (MPS).

    Windows editions:
    - ``cpu`` — CPU only (unless a live CUDA probe appears on a non-frozen run)
    - ``cuda`` — NVIDIA GPU only
    - ``both`` — CPU + NVIDIA GPU (combined installer)
    """
    plat = _platform(platform)
    if _cuda_only_edition_windows(platform=platform):
        return ["cuda"]
    if _both_edition_windows(platform=platform):
        return ["cpu", "cuda"]
    options = ["cpu"]
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
    if _cuda_only_edition_windows(platform=platform):
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
        # NVIDIA-only freeze keeps Faster on CUDA; combined/CPU prefer CPU for Faster.
        device = "cuda" if _cuda_only_edition_windows(platform=platform) else "cpu"
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
    chip = apple_chip_label(probe.cpu_brand)
    chip_bit = f"{chip} · " if chip else ""
    options = desktop_device_options(probe, platform=platform)
    accel = (
        "Apple GPU (MPS)"
        if "mps" in options
        else ("NVIDIA GPU" if "cuda" in options else "CPU")
    )
    return f"This PC: {chip_bit}{ram} · {accel}"


def desktop_recommend_caption(probe: HostProbe, *, platform: str | None = None) -> str:
    rec = desktop_recommend(probe, platform=platform)
    extra = MAC_ACCEL_NOTE if _platform(platform).startswith("darwin") else NVIDIA_ONLY_DISCLAIMER
    return f"{rec['notes']} {extra}"


def lite_accelerator_available(probe: HostProbe, *, platform: str | None = None) -> bool:
    """True when Lite may use a GPU path (MPS or CUDA) on this host."""
    options = desktop_device_options(probe, platform=platform)
    return "mps" in options or "cuda" in options


def lite_auto_speed_id(probe: HostProbe, *, platform: str | None = None) -> str:
    """Speed preset id from installed hardware only (no live memory probe).

    Prefer :func:`lite_auto_choice` when Lite should also respect free RAM.
    """
    return str(desktop_recommend(probe, platform=platform)["speed"])


def lite_auto_choice(
    probe: HostProbe,
    *,
    platform: str | None = None,
    pressure: MemoryPressure | None = None,
) -> dict[str, Any]:
    """Lite device + speed auto, including live memory headroom.

    Starts from :func:`desktop_recommend`. When that would pick MPS/CUDA but
    ``pressure`` is tight, returns CPU + Faster with reason ``low_free_memory``.

    If ``pressure`` is omitted, probes the host once. Probe failure / unknown
    free RAM does not override the hardware recommend.
    """
    if pressure is None:
        pressure = probe_memory_pressure()
    rec = desktop_recommend(probe, platform=platform)
    device = str(rec["device"])
    speed = str(rec["speed"])
    reason: str | None = None
    if device in {"mps", "cuda"} and memory_pressure_is_tight(pressure):
        device = "cpu"
        speed = "faster"
        reason = "low_free_memory"
    return {"device": device, "speed": speed, "reason": reason}


def lite_auto_device(
    probe: HostProbe,
    *,
    platform: str | None = None,
    pressure: MemoryPressure | None = None,
) -> str:
    """Device id Lite should auto-pick (CPU under memory pressure)."""
    return str(lite_auto_choice(probe, platform=platform, pressure=pressure)["device"])


def lite_device_plain_label(device: str) -> str:
    """Short device label for Lite UI (no MPS/CUDA jargon)."""
    if device == "mps":
        return "Apple GPU"
    if device == "cuda":
        return "NVIDIA GPU"
    return "CPU"


def lite_device_choice_ids(
    probe: HostProbe, *, platform: str | None = None
) -> list[str]:
    """CPU + accelerator ids for Lite's Run-on radio, or empty if no choice."""
    if not lite_accelerator_available(probe, platform=platform):
        return []
    options = desktop_device_options(probe, platform=platform)
    if "mps" in options:
        return ["cpu", "mps"]
    # CUDA-only edition lists only cuda; still offer CPU as a Lite escape hatch.
    if "cuda" in options or _cuda_only_edition_windows(platform=platform):
        return ["cpu", "cuda"]
    return []


def _lite_accel_plain_label(probe: HostProbe, *, platform: str | None = None) -> str:
    """Short device label for Lite captions (no MPS/CUDA jargon)."""
    options = desktop_device_options(probe, platform=platform)
    if "mps" in options:
        return "Apple GPU"
    if "cuda" in options:
        return "NVIDIA GPU"
    return "CPU"


def lite_detected_caption(probe: HostProbe, *, platform: str | None = None) -> str:
    """One-line hardware readout for Lite (Detected: Apple M2 Pro · ~16 GB · …)."""
    ram = f"~{probe.ram_gb:g} GB RAM" if probe.ram_gb is not None else "RAM unknown"
    accel = _lite_accel_plain_label(probe, platform=platform)
    chip = apple_chip_label(probe.cpu_brand)
    if chip:
        return f"Detected: {chip} · {ram} · {accel}"
    return f"Detected: {ram} · {accel}"


def lite_using_caption(
    probe: HostProbe,
    *,
    guitar_engine: str,
    platform: str | None = None,
    device: str | None = None,
    speed: str | None = None,
    reason: str | None = None,
) -> str:
    """One-line Lite choice (Using: Faster on CPU · standard guitar model).

    Optional ``device`` / ``speed`` reflect a user Run-on pick; otherwise the
    auto recommendation for this host is used. ``reason="low_free_memory"``
    appends a plain-language note when auto chose CPU for headroom.
    """
    rec = desktop_recommend(probe, platform=platform)
    speed_id = speed if speed is not None else str(rec["speed"])
    speed_label = {"faster": "Faster", "balanced": "Balanced", "best": "Best"}.get(
        speed_id, speed_id.title()
    )
    device_id = device if device is not None else str(rec["device"])
    where = lite_device_plain_label(device_id)
    strong = guitar_engine in {"guitar_roformer", "guitar_roformer_refine"}
    guitar_bit = "strong guitar model" if strong else "standard guitar model"
    line = f"Using: {speed_label} on {where} · {guitar_bit}"
    if reason == "low_free_memory" and device_id == "cpu":
        return f"{line} (low free memory)"
    return line


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
        return "Separating tracks on NVIDIA GPU"
    if device == "mps":
        return "Separating tracks on Apple GPU (Metal)"
    return "Separating tracks. CPU may be slow"
