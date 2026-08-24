"""Host capability detection and processing-mode resolution."""

from __future__ import annotations

import pytest

from backend.capabilities import (
    HostProbe,
    ProcessingModeError,
    build_capabilities,
    recommended_mode,
    resolve_processing_mode,
)
from backend.config import Settings


def _settings(**kwargs) -> Settings:
    defaults = dict(
        env="development",
        secret_key="dev-test-secret",
        require_auth=False,
        max_job_duration_sec=300.0,
        single_flight_jobs=False,
        recommended_mode=None,
    )
    defaults.update(kwargs)
    return Settings(**defaults)


CPU_LOW = HostProbe(cuda=False, mps=False, ram_gb=6.0, single_flight=False)
CPU_MID = HostProbe(cuda=False, mps=False, ram_gb=12.0, single_flight=False)
CPU_UNKNOWN = HostProbe(cuda=False, mps=False, ram_gb=None, single_flight=False)
CUDA_HIGH = HostProbe(cuda=True, mps=False, ram_gb=24.0, single_flight=False)
CUDA_UNKNOWN = HostProbe(cuda=True, mps=False, ram_gb=None, single_flight=False)
MPS_MAC = HostProbe(cuda=False, mps=True, ram_gb=16.0, single_flight=False)
LITE_SF = HostProbe(cuda=False, mps=False, ram_gb=12.0, single_flight=True)


def test_auto_never_selects_extreme_or_high_on_cpu_or_low_ram():
    settings = _settings()
    for probe in (CPU_LOW, CPU_MID, CPU_UNKNOWN, MPS_MAC, LITE_SF):
        mode = recommended_mode(probe, settings)
        assert mode not in ("high_gpu", "extreme")
        resolved = resolve_processing_mode("auto", probe, settings)
        assert resolved.quality != "extreme"
        assert resolved.mode != "high_gpu"
        assert resolved.device != "cuda"


def test_low_ram_or_single_flight_auto_is_lite():
    settings = _settings()
    assert recommended_mode(CPU_LOW, settings) == "lite"
    assert recommended_mode(LITE_SF, settings) == "lite"
    lite = resolve_processing_mode("auto", CPU_LOW, settings)
    assert lite.mode == "lite"
    assert lite.device == "cpu"
    assert lite.quality == "fast"
    assert lite.max_duration_sec == 60.0


def test_cpu_only_mid_or_unknown_ram_auto_is_fast_cpu():
    settings = _settings()
    assert recommended_mode(CPU_MID, settings) == "fast_cpu"
    assert recommended_mode(CPU_UNKNOWN, settings) == "fast_cpu"
    fast = resolve_processing_mode("auto", CPU_MID, settings)
    assert fast.mode == "fast_cpu"
    assert fast.device == "cpu"
    assert fast.quality == "fast"
    assert fast.max_duration_sec == 90.0


def test_cuda_high_ram_auto_is_balanced_not_high():
    settings = _settings()
    assert recommended_mode(CUDA_HIGH, settings) == "balanced"
    assert recommended_mode(CUDA_UNKNOWN, settings) == "balanced"
    resolved = resolve_processing_mode("auto", CUDA_HIGH, settings)
    assert resolved.mode == "balanced"
    assert resolved.device == "cuda"
    assert resolved.quality == "balanced"


def test_high_gpu_rejected_without_cuda():
    settings = _settings()
    with pytest.raises(ProcessingModeError, match="CUDA"):
        resolve_processing_mode("high_gpu", CPU_MID, settings)


def test_high_gpu_enabled_only_with_cuda():
    settings = _settings()
    caps = build_capabilities(CPU_MID, settings)
    high = next(m for m in caps.modes if m.id == "high_gpu")
    assert high.enabled is False
    assert high.reason and "CUDA" in high.reason

    caps_cuda = build_capabilities(CUDA_HIGH, settings)
    high_ok = next(m for m in caps_cuda.modes if m.id == "high_gpu")
    assert high_ok.enabled is True
    resolved = resolve_processing_mode("high_gpu", CUDA_HIGH, settings)
    assert resolved.device == "cuda"
    assert resolved.quality == "high"


def test_balanced_prefers_cuda_then_mps_then_cpu():
    settings = _settings()
    assert resolve_processing_mode("balanced", CUDA_HIGH, settings).device == "cuda"
    assert resolve_processing_mode("balanced", MPS_MAC, settings).device == "mps"
    assert resolve_processing_mode("balanced", CPU_MID, settings).device == "cpu"


def test_auto_on_mps_uses_cpu_not_mps():
    settings = _settings()
    resolved = resolve_processing_mode("auto", MPS_MAC, settings)
    assert resolved.device == "cpu"
    caps = build_capabilities(MPS_MAC, settings)
    assert caps.detected_device == "mps"
    assert "mps" in caps.device_options
    assert caps.recommended_mode == "fast_cpu"


def test_unknown_mode_rejected():
    settings = _settings()
    with pytest.raises(ProcessingModeError, match="unknown"):
        resolve_processing_mode("extreme", CPU_MID, settings)


def test_duration_clamped_to_host_max():
    settings = _settings(max_job_duration_sec=45.0)
    lite = resolve_processing_mode("lite", CPU_LOW, settings)
    assert lite.max_duration_sec == 45.0
    fast = resolve_processing_mode("fast_cpu", CPU_MID, settings)
    assert fast.max_duration_sec == 45.0


def test_recommended_mode_env_override_ignored_if_unrunnable():
    settings = _settings(recommended_mode="high_gpu")
    assert recommended_mode(CPU_MID, settings) == "fast_cpu"
    settings_ok = _settings(recommended_mode="high_gpu")
    assert recommended_mode(CUDA_HIGH, settings_ok) == "high_gpu"


def test_capabilities_modes_expose_max_duration_sec():
    settings = _settings()
    caps = build_capabilities(CPU_MID, settings)
    for mode in caps.modes:
        assert mode.max_duration_sec > 0
    lite = next(m for m in caps.modes if m.id == "lite")
    assert lite.max_duration_sec == 60.0
    fast = next(m for m in caps.modes if m.id == "fast_cpu")
    assert fast.max_duration_sec == 90.0


def test_capabilities_response_shape_has_no_hostname():
    settings = _settings()
    caps = build_capabilities(CUDA_HIGH, settings)
    payload = caps.model_dump()
    assert payload["detected_device"] == "cuda"
    assert payload["recommended_mode"] == "balanced"
    assert payload["ram_gb"] == 24.0
    assert payload["low_ram"] is False
    assert "cpu" in payload["device_options"]
    assert "cuda" in payload["device_options"]
    assert payload["notes"]
    dumped = str(payload).lower()
    assert "hostname" not in dumped
    assert "/users/" not in dumped
    assert "secret" not in dumped


def _cpu_probe(_settings=None):
    return CPU_MID


def test_system_capabilities_endpoint(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from tests.backend_test_utils import configure_backend, fake_wav_bytes, login_headers

    main_mod = configure_backend(tmp_path, monkeypatch, ATT_REQUIRE_AUTH="false")
    monkeypatch.setattr("backend.capabilities.probe_host", _cpu_probe)
    monkeypatch.setattr("backend.main.probe_host", _cpu_probe)
    monkeypatch.setattr("backend.main.get_capabilities", lambda _s: build_capabilities(CPU_MID, main_mod.settings))

    with TestClient(main_mod.app) as client:
        res = client.get("/v1/system/capabilities")
    assert res.status_code == 200
    body = res.json()
    assert body["detected_device"] == "cpu"
    assert body["recommended_mode"] == "fast_cpu"
    assert "cpu" in body["device_options"]
    assert "cuda" not in body["device_options"]
    high = next(m for m in body["modes"] if m["id"] == "high_gpu")
    assert high["enabled"] is False
    assert "CUDA" in high["reason"]


def test_isolate_high_gpu_rejected_without_cuda(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from tests.backend_test_utils import configure_backend, fake_wav_bytes, login_headers

    main_mod = configure_backend(tmp_path, monkeypatch, ATT_REQUIRE_AUTH="false")
    monkeypatch.setattr("backend.main.probe_host", _cpu_probe)

    with TestClient(main_mod.app) as client:
        headers = login_headers(client)
        upload = client.post(
            "/v1/uploads/audio",
            headers=headers,
            files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
        )
        assert upload.status_code == 200
        blocked = client.post(
            "/v1/isolate/jobs",
            headers=headers,
            json={
                "upload_id": upload.json()["upload_id"],
                "model": "htdemucs",
                "processing_mode": "high_gpu",
            },
        )
    assert blocked.status_code == 400
    assert "CUDA" in blocked.json()["detail"]


def test_isolate_auto_uses_resolved_cpu_fast_not_hardcoded_quality_only(tmp_path, monkeypatch):
    from pathlib import Path

    from fastapi.testclient import TestClient

    from tests.backend_test_utils import configure_backend, fake_wav_bytes, login_headers

    main_mod = configure_backend(tmp_path, monkeypatch, ATT_REQUIRE_AUTH="false")
    monkeypatch.setattr("backend.main.probe_host", _cpu_probe)

    def fake_separate_stems(audio_path, output_dir, config=None, on_progress=None):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {}
        for name in ("vocals", "drums", "bass", "other"):
            p = output_dir / f"{name}.wav"
            p.write_bytes(b"stem")
            artifacts[name] = p
        if on_progress:
            on_progress("done", "ok")
        return artifacts

    monkeypatch.setattr("backend.jobs.runner.separate_stems", fake_separate_stems)

    with TestClient(main_mod.app) as client:
        headers = login_headers(client)
        upload = client.post(
            "/v1/uploads/audio",
            headers=headers,
            files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
        )
        job = client.post(
            "/v1/isolate/jobs",
            headers=headers,
            json={
                "upload_id": upload.json()["upload_id"],
                "model": "htdemucs",
                "processing_mode": "auto",
                "quality": "extreme",
                "device": "cuda",
            },
        )
    assert job.status_code == 200, job.text
    record = main_mod.job_manager.get(job.json()["id"])
    assert record is not None
    assert record.isolate_device == "cpu"
    assert record.isolate_quality == "fast"
    assert record.max_duration_sec == 90.0


def test_tab_processing_mode_persists_demucs_device(tmp_path, monkeypatch):
    from pathlib import Path

    from fastapi.testclient import TestClient

    from tests.backend_test_utils import configure_backend, fake_wav_bytes, login_headers

    main_mod = configure_backend(tmp_path, monkeypatch, ATT_REQUIRE_AUTH="false")
    monkeypatch.setattr("backend.main.probe_host", _cpu_probe)

    def fake_pipeline(**kwargs):
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf = output_dir / "transcription.pdf"
        midi = output_dir / "transcription.mid"
        pdf.write_bytes(b"pdf")
        midi.write_bytes(b"midi")
        cfg = kwargs["config"]
        assert cfg.demucs_device == "cpu"
        assert cfg.demucs_quality == "fast"
        return {"pdf": pdf, "midi": midi}

    monkeypatch.setattr("backend.jobs.runner.run_pipeline", fake_pipeline)

    with TestClient(main_mod.app) as client:
        headers = login_headers(client)
        upload = client.post(
            "/v1/uploads/audio",
            headers=headers,
            files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
        )
        job = client.post(
            "/v1/jobs",
            headers=headers,
            json={
                "upload_id": upload.json()["upload_id"],
                "separate_stems": True,
                "processing_mode": "lite",
            },
        )
    assert job.status_code == 200, job.text
    record = main_mod.job_manager.get(job.json()["id"])
    assert record is not None
    assert record.demucs_device == "cpu"
    assert record.demucs_quality == "fast"
    assert record.max_duration_sec == 60.0


def test_legacy_isolate_cuda_device_rejected_without_cuda(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from tests.backend_test_utils import configure_backend, fake_wav_bytes, login_headers

    main_mod = configure_backend(tmp_path, monkeypatch, ATT_REQUIRE_AUTH="false")
    monkeypatch.setattr("backend.main.probe_host", _cpu_probe)

    with TestClient(main_mod.app) as client:
        headers = login_headers(client)
        upload = client.post(
            "/v1/uploads/audio",
            headers=headers,
            files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
        )
        blocked = client.post(
            "/v1/isolate/jobs",
            headers=headers,
            json={
                "upload_id": upload.json()["upload_id"],
                "model": "htdemucs",
                "quality": "fast",
                "device": "cuda",
            },
        )
    assert blocked.status_code == 400
    assert "cuda" in blocked.json()["detail"].lower()

