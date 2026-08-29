"""Desktop hardware probe and isolation speed recommendations."""

from __future__ import annotations

import pytest

from audio_to_tab.hardware import (
    CUDA_UNAVAILABLE_MESSAGE,
    MAC_NO_NVIDIA_NOTE,
    NVIDIA_ONLY_DISCLAIMER,
    HostProbe,
    desktop_device_options,
    desktop_recommend,
    desktop_recommend_caption,
    desktop_system_summary,
    ensure_cuda_available,
    get_desktop_probe_without_torch,
    resolve_desktop_speed,
    separate_progress_message,
)

CPU_LOW = HostProbe(cuda=False, mps=False, ram_gb=6.0)
CPU_MID = HostProbe(cuda=False, mps=False, ram_gb=12.0)
CUDA_HIGH = HostProbe(cuda=True, mps=False, ram_gb=24.0)
CUDA_LOW = HostProbe(cuda=True, mps=False, ram_gb=6.0)
MPS_MAC = HostProbe(cuda=False, mps=True, ram_gb=16.0)


def test_mac_never_offers_cuda_even_if_probe_says_cuda():
    fake_cuda = HostProbe(cuda=True, mps=True, ram_gb=16.0)
    assert desktop_device_options(fake_cuda, platform="darwin") == ["cpu"]
    assert desktop_device_options(CUDA_HIGH, platform="darwin") == ["cpu"]


def test_windows_offers_cuda_only_when_probe_has_cuda():
    assert desktop_device_options(CPU_MID, platform="win32") == ["cpu"]
    assert desktop_device_options(CUDA_HIGH, platform="win32") == ["cpu", "cuda"]


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
        (MPS_MAC, "darwin"),
    ):
        rec = desktop_recommend(probe, platform=plat)
        assert rec["device"] == "cpu"
        assert rec["speed"] == "faster"
        assert rec["quality"] == "fast"


def test_resolve_faster_always_cpu():
    resolved = resolve_desktop_speed("faster", CUDA_HIGH, platform="win32")
    assert resolved["device"] == "cpu"
    assert resolved["quality"] == "fast"


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
    mac = desktop_system_summary(MPS_MAC, platform="darwin")
    assert "CPU" in mac

    cap_win = desktop_recommend_caption(CUDA_HIGH, platform="win32")
    assert NVIDIA_ONLY_DISCLAIMER in cap_win
    assert "NVIDIA" in cap_win
    cap_mac = desktop_recommend_caption(MPS_MAC, platform="darwin")
    assert MAC_NO_NVIDIA_NOTE in cap_mac
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


def test_get_desktop_probe_without_torch_does_not_import_torch(monkeypatch):
    import inspect

    src = inspect.getsource(get_desktop_probe_without_torch)
    assert "probe_torch" not in src
    assert "import torch" not in src.split('"""')[-1]
    probe = get_desktop_probe_without_torch()
    assert probe.cuda is False
    assert probe.mps is False
    assert probe.ram_gb is None or probe.ram_gb > 0
