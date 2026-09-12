"""Host processing capability detection and processing-mode resolution."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from audio_to_tab.hardware import (
    LOW_RAM_GB,
    MPS_MIN_RAM_GB,
    HostProbe,
    probe_cpu_brand,
    probe_ram_gb,
    probe_torch,
)
from backend.config import Settings

MODE_AUTO = "auto"
MODE_FAST_CPU = "fast_cpu"
MODE_BALANCED = "balanced"
MODE_HIGH_GPU = "high_gpu"
MODE_LITE = "lite"

CONCRETE_MODES = (MODE_FAST_CPU, MODE_BALANCED, MODE_HIGH_GPU, MODE_LITE)
ALL_MODES = (MODE_AUTO, *CONCRETE_MODES)

MODE_LABELS = {
    MODE_AUTO: "Auto",
    MODE_FAST_CPU: "Fast (CPU)",
    MODE_BALANCED: "Balanced",
    MODE_HIGH_GPU: "High (GPU)",
    MODE_LITE: "Low RAM (60 s)",
}

FAST_CPU_DURATION_SEC = 90.0
LITE_DURATION_SEC = 60.0
HIGH_RAM_GB = 16.0


class ProcessingModeError(ValueError):
    """Raised when a processing mode cannot run on this host."""


@dataclass(frozen=True)
class ResolvedProcessing:
    mode: str
    device: str
    quality: str
    max_duration_sec: float


class ModeInfo(BaseModel):
    id: str
    label: str
    enabled: bool
    reason: str | None = None
    device: str
    max_duration_sec: float


class CapabilitiesResponse(BaseModel):
    device_options: list[str]
    recommended_mode: str
    detected_device: str
    ram_gb: float | None
    notes: str
    low_ram: bool
    allow_youtube: bool = False
    modes: list[ModeInfo]


def probe_host(settings: Settings) -> HostProbe:
    cuda, mps = probe_torch()
    return HostProbe(
        cuda=cuda,
        mps=mps,
        ram_gb=probe_ram_gb(),
        single_flight=bool(settings.single_flight_jobs),
        cpu_brand=probe_cpu_brand(),
    )


def detected_device(probe: HostProbe) -> str:
    if probe.cuda:
        return "cuda"
    if probe.mps:
        return "mps"
    return "cpu"


def mps_eligible(probe: HostProbe) -> bool:
    """Apple GPU listed only when torch-MPS is up and RAM meets the desktop gate."""
    return bool(probe.mps) and (probe.ram_gb is None or probe.ram_gb >= MPS_MIN_RAM_GB)


def device_options(probe: HostProbe) -> list[str]:
    options = ["cpu"]
    if probe.cuda:
        options.append("cuda")
    if mps_eligible(probe):
        options.append("mps")
    return options


def is_low_ram(probe: HostProbe) -> bool:
    return probe.ram_gb is not None and probe.ram_gb < LOW_RAM_GB


def is_lite_host(probe: HostProbe) -> bool:
    return probe.single_flight or is_low_ram(probe)


def balanced_device(probe: HostProbe) -> str:
    if probe.cuda:
        return "cuda"
    if mps_eligible(probe):
        return "mps"
    return "cpu"


def _mode_runnable(mode: str, probe: HostProbe) -> bool:
    if mode == MODE_HIGH_GPU:
        return probe.cuda
    return mode in CONCRETE_MODES


def recommended_mode(probe: HostProbe, settings: Settings) -> str:
    override = (settings.recommended_mode or "").strip()
    if override in CONCRETE_MODES and _mode_runnable(override, probe):
        return override

    if is_lite_host(probe):
        return MODE_LITE
    if probe.cuda:
        return MODE_BALANCED
    if mps_eligible(probe):
        return MODE_BALANCED
    return MODE_FAST_CPU


def _mode_cap(mode: str, settings: Settings) -> float:
    if mode == MODE_LITE:
        return LITE_DURATION_SEC
    if mode == MODE_FAST_CPU:
        return FAST_CPU_DURATION_SEC
    return settings.max_job_duration_sec


def _clamp_duration(mode: str, settings: Settings, requested: float | None) -> float:
    cap = min(_mode_cap(mode, settings), settings.max_job_duration_sec)
    if requested is None:
        return cap
    return min(requested, cap)


def _settings_for_mode(mode: str, probe: HostProbe, settings: Settings) -> ResolvedProcessing:
    if mode == MODE_LITE:
        device, quality = "cpu", "fast"
    elif mode == MODE_FAST_CPU:
        device, quality = "cpu", "fast"
    elif mode == MODE_BALANCED:
        device, quality = balanced_device(probe), "balanced"
    elif mode == MODE_HIGH_GPU:
        device, quality = "cuda", "high"
    else:
        raise ProcessingModeError(f"unknown processing mode: {mode}")
    return ResolvedProcessing(
        mode=mode,
        device=device,
        quality=quality,
        max_duration_sec=_clamp_duration(mode, settings, None),
    )


def resolve_processing_mode(
    mode: str,
    probe: HostProbe,
    settings: Settings,
    *,
    requested_duration_sec: float | None = None,
) -> ResolvedProcessing:
    if mode == MODE_AUTO:
        mode = recommended_mode(probe, settings)
    if mode not in CONCRETE_MODES:
        raise ProcessingModeError(f"unknown processing mode: {mode}")
    if not _mode_runnable(mode, probe):
        if mode == MODE_HIGH_GPU:
            raise ProcessingModeError(
                "High (GPU) needs NVIDIA CUDA on this host. Choose Auto, Fast (CPU), Balanced, or Lite."
            )
        raise ProcessingModeError(f"processing mode {mode} is not available on this host")

    resolved = _settings_for_mode(mode, probe, settings)
    duration = _clamp_duration(mode, settings, requested_duration_sec)
    return ResolvedProcessing(
        mode=resolved.mode,
        device=resolved.device,
        quality=resolved.quality,
        max_duration_sec=duration,
    )


def _notes(probe: HostProbe, rec: str) -> str:
    parts: list[str] = []
    if probe.cuda:
        parts.append("CUDA available.")
    elif mps_eligible(probe):
        parts.append("Apple GPU (MPS) available (≥12 GB RAM).")
    elif probe.mps:
        parts.append("Apple GPU (MPS) detected; Auto stays on CPU below 12 GB RAM.")
    else:
        parts.append("CUDA not available; jobs run on CPU.")
    if is_low_ram(probe):
        parts.append("Low RAM host; Auto uses Low RAM (60 s).")
    elif probe.single_flight:
        parts.append("Single-flight jobs enabled; Auto uses Low RAM (60 s).")
    if rec == MODE_FAST_CPU:
        parts.append("Auto picks Fast (CPU).")
    elif rec == MODE_BALANCED:
        parts.append("Auto picks Balanced.")
    elif rec == MODE_LITE:
        parts.append("Auto picks Low RAM (60 s).")
    elif rec == MODE_HIGH_GPU:
        parts.append("Auto override: High (GPU).")
    return " ".join(parts)


def build_capabilities(probe: HostProbe, settings: Settings) -> CapabilitiesResponse:
    rec = recommended_mode(probe, settings)
    options = device_options(probe)
    detected = detected_device(probe)
    modes: list[ModeInfo] = []
    for mode_id in ALL_MODES:
        if mode_id == MODE_AUTO:
            resolved = _settings_for_mode(rec, probe, settings)
            modes.append(
                ModeInfo(
                    id=MODE_AUTO,
                    label=MODE_LABELS[MODE_AUTO],
                    enabled=True,
                    reason=None,
                    device=resolved.device,
                    max_duration_sec=resolved.max_duration_sec,
                )
            )
            continue
        enabled = _mode_runnable(mode_id, probe)
        reason = None if enabled else "Needs NVIDIA CUDA on this host"
        resolved = _settings_for_mode(mode_id, probe, settings) if enabled else None
        device = resolved.device if resolved else "cuda"
        cap = resolved.max_duration_sec if resolved else _mode_cap(mode_id, settings)
        modes.append(
            ModeInfo(
                id=mode_id,
                label=MODE_LABELS[mode_id],
                enabled=enabled,
                reason=reason,
                device=device,
                max_duration_sec=cap,
            )
        )
    return CapabilitiesResponse(
        device_options=options,
        recommended_mode=rec,
        detected_device=detected,
        ram_gb=probe.ram_gb,
        notes=_notes(probe, rec),
        low_ram=is_low_ram(probe),
        allow_youtube=bool(settings.allow_youtube),
        modes=modes,
    )


def get_capabilities(settings: Settings) -> CapabilitiesResponse:
    return build_capabilities(probe_host(settings), settings)


def assert_device_allowed(device: str, probe: HostProbe) -> None:
    allowed = device_options(probe)
    if device not in allowed:
        raise ProcessingModeError(
            f"device {device!r} is not available on this host. Choose from: {', '.join(allowed)}"
        )
