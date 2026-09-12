"""Desktop hardware probe and isolation speed recommendations."""

from __future__ import annotations

import pytest

from audio_to_tab.hardware import (
    CUDA_UNAVAILABLE_MESSAGE,
    MAC_ACCEL_NOTE,
    NVIDIA_ONLY_DISCLAIMER,
    HostProbe,
    apple_chip_label,
    desktop_device_options,
    desktop_recommend,
    desktop_recommend_caption,
    desktop_system_summary,
    ensure_cuda_available,
    get_desktop_probe_without_torch,
    lite_accelerator_available,
    lite_auto_speed_id,
    lite_detected_caption,
    lite_device_choice_ids,
    lite_device_plain_label,
    lite_using_caption,
    recommended_cpu_threads,
    apply_recommended_cpu_threads,
    cpu_thread_env,
    roformer_max_audio_sec,
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


def test_cpu_thread_env_keys():
    env = cpu_thread_env(ram_gb=8.0)
    assert env["OMP_NUM_THREADS"] == env["MKL_NUM_THREADS"] == env["TORCH_NUM_THREADS"]
    assert int(env["OMP_NUM_THREADS"]) >= 1


def test_apply_recommended_cpu_threads_skips_gpu():
    assert apply_recommended_cpu_threads(device="mps") is None
    assert apply_recommended_cpu_threads(device="cuda") is None


def test_roformer_max_audio_sec():
    low = HostProbe(cuda=False, mps=False, ram_gb=8.0)
    high = HostProbe(cuda=False, mps=True, ram_gb=16.0)
    unknown = HostProbe(cuda=False, mps=False, ram_gb=None)
    assert roformer_max_audio_sec(low) == 90.0
    assert roformer_max_audio_sec(high) == 180.0
    assert roformer_max_audio_sec(unknown) == 180.0
    assert roformer_max_audio_sec(HostProbe(cuda=False, mps=False, ram_gb=11.9)) == 90.0
    assert roformer_max_audio_sec(HostProbe(cuda=False, mps=False, ram_gb=12.0)) == 180.0


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
    monkeypatch.setattr("audio_to_tab.hardware.sys.platform", "win32")
    probe = get_desktop_probe_without_torch()
    assert probe.cuda is True


def test_lite_accelerator_gate_by_ram_and_platform():
    eight = HostProbe(cuda=False, mps=True, ram_gb=8.0)
    assert lite_accelerator_available(eight, platform="darwin") is False
    assert lite_accelerator_available(MPS_MAC, platform="darwin") is True
    assert lite_accelerator_available(CUDA_HIGH, platform="win32") is True
    assert lite_accelerator_available(CUDA_HIGH, platform="darwin") is False
    assert lite_accelerator_available(CPU_MID, platform="win32") is False


def test_lite_device_choice_ids_cpu_plus_accelerator():
    eight = HostProbe(cuda=False, mps=True, ram_gb=8.0)
    assert lite_device_choice_ids(eight, platform="darwin") == []
    assert lite_device_choice_ids(MPS_MAC, platform="darwin") == ["cpu", "mps"]
    assert lite_device_choice_ids(CUDA_HIGH, platform="win32") == ["cpu", "cuda"]
    assert lite_device_choice_ids(CPU_MID, platform="win32") == []
    assert lite_device_plain_label("mps") == "Apple GPU"
    assert lite_device_plain_label("cuda") == "NVIDIA GPU"
    assert lite_device_plain_label("cpu") == "CPU"


def test_lite_auto_speed_matches_desktop_recommend():
    eight = HostProbe(cuda=False, mps=True, ram_gb=8.0)
    assert lite_auto_speed_id(eight, platform="darwin") == "faster"
    assert lite_auto_speed_id(MPS_MAC, platform="darwin") == "balanced"
    assert lite_auto_speed_id(CUDA_HIGH, platform="win32") == "balanced"


def test_lite_detected_and_using_captions_plain_language():
    eight = HostProbe(cuda=False, mps=True, ram_gb=8.0)
    detected = lite_detected_caption(eight, platform="darwin")
    assert detected.startswith("Detected:")
    assert "8" in detected
    assert "CPU" in detected
    assert "MPS" not in detected

    m2 = HostProbe(
        cuda=False, mps=True, ram_gb=16.0, cpu_brand="Apple M2 Pro"
    )
    detected_m2 = lite_detected_caption(m2, platform="darwin")
    assert "Apple M2 Pro" in detected_m2
    assert "16" in detected_m2
    assert "Apple GPU" in detected_m2

    intel = HostProbe(
        cuda=False,
        mps=False,
        ram_gb=16.0,
        cpu_brand="Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz",
    )
    detected_intel = lite_detected_caption(intel, platform="darwin")
    assert "Intel" not in detected_intel
    assert "CPU" in detected_intel

    using_cpu = lite_using_caption(
        eight, guitar_engine="guitar_demucs_6s", platform="darwin"
    )
    assert using_cpu.startswith("Using:")
    assert "Faster" in using_cpu
    assert "CPU" in using_cpu
    assert "standard guitar model" in using_cpu
    assert "Demucs" not in using_cpu
    assert "RoFormer" not in using_cpu

    using_mps = lite_using_caption(
        MPS_MAC, guitar_engine="guitar_roformer", platform="darwin"
    )
    assert "Balanced" in using_mps
    assert "Apple GPU" in using_mps
    assert "strong guitar model" in using_mps
    assert "MPS" not in using_mps

    using_cuda = lite_using_caption(
        CUDA_HIGH, guitar_engine="guitar_roformer", platform="win32"
    )
    assert "NVIDIA GPU" in using_cuda

    # User Run-on override (Lite radio) must drive the Using caption.
    using_override = lite_using_caption(
        MPS_MAC,
        guitar_engine="guitar_roformer",
        platform="darwin",
        device="cpu",
        speed="faster",
    )
    assert "Faster" in using_override
    assert "CPU" in using_override
    assert "Apple GPU" not in using_override


def test_apple_chip_label_only_keeps_apple_brands():
    assert apple_chip_label("Apple M2 Pro") == "Apple M2 Pro"
    assert apple_chip_label("  Apple M1  ") == "Apple M1"
    assert apple_chip_label("Intel(R) Core(TM) i7") is None
    assert apple_chip_label(None) is None


def test_desktop_system_summary_includes_apple_chip():
    probe = HostProbe(
        cuda=False, mps=True, ram_gb=16.0, cpu_brand="Apple M2 Pro"
    )
    summary = desktop_system_summary(probe, platform="darwin")
    assert "Apple M2 Pro" in summary
    assert "Apple GPU" in summary


def test_refuse_long_roformer_audio(tmp_path, monkeypatch):
    from audio_to_tab.roformer import _refuse_long_roformer_audio, run_roformer_model

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"x")
    monkeypatch.setattr(
        "audio_to_tab.isolate.probe_duration_sec", lambda _path: 400.0
    )
    monkeypatch.setattr(
        "audio_to_tab.hardware.roformer_max_audio_sec", lambda _probe=None: 90.0
    )
    monkeypatch.setattr(
        "audio_to_tab.hardware.get_desktop_probe",
        lambda **_k: HostProbe(cuda=False, mps=False, ram_gb=8.0),
    )
    with pytest.raises(RuntimeError, match="90"):
        _refuse_long_roformer_audio(audio)
    with pytest.raises(RuntimeError, match="90"):
        run_roformer_model(audio, tmp_path, model="bs_roformer_sw", device="cpu")
