"""Desktop hardware probe and isolation speed recommendations."""

from __future__ import annotations

import pytest

from audio_to_tab.hardware import (
    CUDA_UNAVAILABLE_MESSAGE,
    MAC_ACCEL_NOTE,
    NVIDIA_ONLY_DISCLAIMER,
    HostProbe,
    desktop_device_options,
    desktop_recommend,
    desktop_recommend_caption,
    desktop_system_summary,
    ensure_cuda_available,
    get_desktop_probe_without_torch,
    recommended_cpu_threads,
    resolve_desktop_speed,
    resolve_safe_device,
    separate_progress_message,
)

CPU_LOW = HostProbe(cuda=False, mps=False, ram_gb=6.0)
CPU_MID = HostProbe(cuda=False, mps=False, ram_gb=12.0)
CUDA_HIGH = HostProbe(cuda=True, mps=False, ram_gb=24.0)
CUDA_LOW = HostProbe(cuda=True, mps=False, ram_gb=6.0)
MPS_MAC = HostProbe(cuda=False, mps=True, ram_gb=16.0)


@pytest.fixture(autouse=True)
def _cpu_edition_by_default(monkeypatch):
    """Most tests assume the CPU desktop edition unless they set AUDIO_TOOLS_EDITION."""
    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)


def test_mac_offers_mps_but_never_cuda():
    fake_cuda = HostProbe(cuda=True, mps=True, ram_gb=16.0)
    assert desktop_device_options(fake_cuda, platform="darwin") == ["cpu", "mps"]
    assert desktop_device_options(CUDA_HIGH, platform="darwin") == ["cpu"]

def test_mac_mps_gated_behind_12gb_ram():
    eight = HostProbe(cuda=False, mps=True, ram_gb=8.0)
    assert desktop_device_options(eight, platform="darwin") == ["cpu"]


def test_windows_offers_cuda_only_when_probe_has_cuda():
    assert desktop_device_options(CPU_MID, platform="win32") == ["cpu"]
    assert desktop_device_options(CUDA_HIGH, platform="win32") == ["cpu", "cuda"]

def test_mac_never_offers_mps_on_windows():
    assert desktop_device_options(MPS_MAC, platform="win32") == ["cpu"]


def test_linux_desktop_policy_matches_windows_not_mac():
    # desktop_device_options is win-or-cpu; Linux testers are not the Mac exception.
    assert desktop_device_options(CUDA_HIGH, platform="linux") == ["cpu"]


def test_auto_low_ram_is_faster_cpu_even_with_cuda():
    rec = desktop_recommend(CUDA_LOW, platform="win32")
    assert rec["speed"] == "faster"
    assert rec["device"] == "cpu"
    assert rec["quality"] == "fast"
    assert "short clip" in rec["notes"]


def test_auto_windows_cuda_is_balanced_gpu():
    rec = desktop_recommend(CUDA_HIGH, platform="win32")
    assert rec["speed"] == "balanced"
    assert rec["device"] == "cuda"
    assert rec["quality"] == "balanced"


def test_auto_cpu_or_mac_is_faster_cpu():
    for probe, plat in (
        (CPU_MID, "win32"),
        (CPU_MID, "darwin"),
        (CUDA_HIGH, "darwin"),
    ):
        rec = desktop_recommend(probe, platform=plat)
        assert rec["device"] == "cpu"
        assert rec["speed"] == "faster"
        assert rec["quality"] == "fast"


def test_auto_mps_mac_is_balanced_gpu():
    rec = desktop_recommend(MPS_MAC, platform="darwin")
    assert rec["device"] == "mps"
    assert rec["speed"] == "balanced"
    assert rec["quality"] == "balanced"


def test_auto_low_ram_mps_mac_stays_cpu():
    low = HostProbe(cuda=False, mps=True, ram_gb=8.0)
    rec = desktop_recommend(low, platform="darwin")
    assert rec["device"] == "cpu"
    assert rec["speed"] == "faster"


def test_resolve_faster_always_cpu_on_cpu_edition(monkeypatch):
    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)
    resolved = resolve_desktop_speed("faster", CUDA_HIGH, platform="win32")
    assert resolved["device"] == "cpu"
    assert resolved["quality"] == "fast"


def test_resolve_faster_uses_cuda_on_cuda_edition(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "cuda")
    resolved = resolve_desktop_speed("faster", CPU_MID, platform="win32")
    assert resolved["device"] == "cuda"
    assert resolved["quality"] == "fast"


def test_cuda_edition_windows_device_options_cuda_only(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "cuda")
    assert desktop_device_options(CPU_MID, platform="win32") == ["cuda"]


def test_cuda_edition_system_summary_shows_nvidia_not_cpu(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "cuda")
    summary = desktop_system_summary(CPU_MID, platform="win32")
    assert "NVIDIA GPU" in summary
    assert " · CPU" not in summary


def test_resolve_balanced_and_best_use_cuda_on_windows_when_available():
    balanced = resolve_desktop_speed("balanced", CUDA_HIGH, platform="win32")
    assert balanced["device"] == "cuda"
    assert balanced["quality"] == "balanced"
    best = resolve_desktop_speed("best", CUDA_HIGH, platform="win32")
    assert best["device"] == "cuda"
    assert best["quality"] == "high"


def test_resolve_balanced_stays_cpu_on_mac():
    resolved = resolve_desktop_speed("balanced", CUDA_HIGH, platform="darwin")
    assert resolved["device"] == "cpu"


def test_resolve_unknown_speed_is_balanced():
    auto = resolve_desktop_speed("auto", CUDA_HIGH, platform="win32")
    assert auto["id"] == "balanced"
    assert auto["quality"] == "balanced"
    assert auto["device"] == "cuda"
    unknown = resolve_desktop_speed("nope", CPU_MID, platform="win32")
    assert unknown["id"] == "balanced"
    assert unknown["quality"] == "balanced"
    assert unknown["device"] == "cpu"


def test_system_summary_and_disclaimer_copy():
    win_gpu = desktop_system_summary(CUDA_HIGH, platform="win32")
    assert "NVIDIA GPU" in win_gpu
    assert "24" in win_gpu
    win_cpu = desktop_system_summary(CPU_MID, platform="win32")
    assert "CPU" in win_cpu
    mac_mps = desktop_system_summary(MPS_MAC, platform="darwin")
    assert "Apple GPU (MPS)" in mac_mps
    mac_cpu = desktop_system_summary(HostProbe(cuda=False, mps=False, ram_gb=16.0), platform="darwin")
    assert "CPU" in mac_cpu

    cap_win = desktop_recommend_caption(CUDA_HIGH, platform="win32")
    assert NVIDIA_ONLY_DISCLAIMER in cap_win
    assert "NVIDIA" in cap_win
    cap_mac = desktop_recommend_caption(MPS_MAC, platform="darwin")
    assert MAC_ACCEL_NOTE in cap_mac
    assert NVIDIA_ONLY_DISCLAIMER not in cap_mac


def test_ensure_cuda_available_fail_closed():
    ensure_cuda_available("cpu", CPU_MID)
    with pytest.raises(RuntimeError, match="NVIDIA CUDA"):
        ensure_cuda_available("cuda", CPU_MID)
    assert "NVIDIA" in CUDA_UNAVAILABLE_MESSAGE


def test_separate_progress_mentions_device():
    assert "CPU" in separate_progress_message("cpu")
    assert "NVIDIA GPU" in separate_progress_message("cuda")
    assert "CPU" not in separate_progress_message("cuda")
    assert "Apple GPU" in separate_progress_message("mps")
    assert "CPU" not in separate_progress_message("mps")


def test_recommended_cpu_threads_clamps_by_ram(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "")
    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)

    def threads_for(ram_gb):
        return recommended_cpu_threads(ram_gb=ram_gb)

    assert threads_for(8.0) <= 4 or threads_for(8.0) >= 2
    assert threads_for(16.0) >= 4
    assert threads_for(64.0) >= 4
    assert threads_for(16.0) >= threads_for(8.0)
    assert recommended_cpu_threads(ram_gb=None) >= 1


def test_resolve_safe_device_downgrades_ineligible_mps():
    assert resolve_safe_device("cpu", CPU_MID) == "cpu"
    with pytest.raises(RuntimeError, match="NVIDIA CUDA"):
        resolve_safe_device("cuda", CPU_MID)
    assert resolve_safe_device("mps", MPS_MAC) == "mps"
    low = HostProbe(cuda=False, mps=True, ram_gb=8.0)
    assert resolve_safe_device("mps", low) == "cpu"


def test_get_desktop_probe_without_torch_does_not_import_torch(monkeypatch):
    import inspect

    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)
    src = inspect.getsource(get_desktop_probe_without_torch)
    assert "probe_torch" not in src
    assert "import torch" not in src.split('"""')[-1]
    probe = get_desktop_probe_without_torch()
    assert probe.cuda is False
    assert probe.mps is False
    assert probe.ram_gb is None or probe.ram_gb > 0


def test_get_desktop_probe_without_torch_cuda_edition(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "cuda")
    probe = get_desktop_probe_without_torch()
    assert probe.cuda is True
