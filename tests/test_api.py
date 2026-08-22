"""API smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

from tests.backend_test_utils import configure_backend, fake_wav_bytes, login_headers


@pytest.fixture
def client(tmp_path, monkeypatch):
    main_mod = configure_backend(tmp_path, monkeypatch, ATT_REQUIRE_AUTH="false")
    with TestClient(main_mod.app) as c:
        yield c


@pytest.fixture
def headers(client):
    return login_headers(client)


def test_health(client):
    res = client.get("/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_system_capabilities_smoke(client):
    res = client.get("/v1/system/capabilities")
    assert res.status_code == 200
    body = res.json()
    assert body["detected_device"] in ("cpu", "cuda", "mps")
    assert body["recommended_mode"] in ("fast_cpu", "balanced", "high_gpu", "lite")
    assert "cpu" in body["device_options"]
    assert "notes" in body
    assert isinstance(body["modes"], list)
    assert any(m["id"] == "auto" for m in body["modes"])


def test_isolate_job_request_defaults_to_full_song():
    from backend.contracts import IsolateJobCreateRequest

    req = IsolateJobCreateRequest(upload_id="x")
    assert req.start_sec == 0.0
    assert req.end_sec is None
    assert req.max_duration_sec is None
    assert req.lead_rhythm is False
    assert req.dual_guitar is False
    assert req.quality == "fast"


def test_isolate_job_request_rejects_invalid_region():
    import pytest
    from pydantic import ValidationError

    from backend.contracts import IsolateJobCreateRequest

    with pytest.raises(ValidationError):
        IsolateJobCreateRequest(upload_id="x", start_sec=60, end_sec=30)
    with pytest.raises(ValidationError):
        IsolateJobCreateRequest(upload_id="x", start_sec=10, end_sec=12)


def test_isolate_job_region_passes_config(client, headers, monkeypatch):
    from audio_to_tab.isolate import IsolateConfig

    upload = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
    )
    assert upload.status_code == 200
    upload_id = upload.json()["upload_id"]

    seen_configs: list[IsolateConfig] = []

    def fake_separate_stems(audio_path, output_dir, config=None, on_progress=None):
        seen_configs.append(config or IsolateConfig())
        from pathlib import Path

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {}
        for name in ("vocals", "drums"):
            p = output_dir / f"{name}.wav"
            p.write_bytes(b"stem")
            artifacts[name] = p
        if on_progress:
            on_progress("done", "ok")
        return artifacts

    monkeypatch.setattr("backend.jobs.runner.separate_stems", fake_separate_stems)

    job = client.post(
        "/v1/isolate/jobs",
        headers=headers,
        json={
            "upload_id": upload_id,
            "model": "htdemucs",
            "quality": "fast",
            "start_sec": 30,
            "end_sec": 75,
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    import time

    status = None
    for _ in range(60):
        status = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)

    assert status is not None
    assert status["status"] == "succeeded", status.get("error")
    assert seen_configs
    cfg = seen_configs[0]
    assert cfg.start_sec == 30.0
    assert cfg.max_duration_sec == 45.0


def test_isolate_job_lite_clamps_region_length(client, headers, monkeypatch):
    from audio_to_tab.isolate import IsolateConfig
    from backend.capabilities import HostProbe

    upload = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
    )
    upload_id = upload.json()["upload_id"]

    seen_configs: list[IsolateConfig] = []

    def fake_separate_stems(audio_path, output_dir, config=None, on_progress=None):
        seen_configs.append(config or IsolateConfig())
        from pathlib import Path

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        p = output_dir / "vocals.wav"
        p.write_bytes(b"stem")
        if on_progress:
            on_progress("done", "ok")
        return {"vocals": p}

    monkeypatch.setattr("backend.jobs.runner.separate_stems", fake_separate_stems)
    monkeypatch.setattr(
        "backend.main.probe_host",
        lambda _s: HostProbe(cuda=False, mps=False, ram_gb=6.0, single_flight=False),
    )

    job = client.post(
        "/v1/isolate/jobs",
        headers=headers,
        json={
            "upload_id": upload_id,
            "model": "htdemucs",
            "processing_mode": "lite",
            "start_sec": 0,
            "end_sec": 120,
        },
    )
    assert job.status_code == 200

    import time

    job_id = job.json()["id"]
    for _ in range(60):
        status = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)

    assert seen_configs
    cfg = seen_configs[0]
    assert cfg.start_sec == 0.0
    assert cfg.max_duration_sec == 60.0


def test_isolate_job_request_dual_guitar_aliases_lead_rhythm():
    from backend.contracts import IsolateJobCreateRequest

    req = IsolateJobCreateRequest(upload_id="x", dual_guitar=True)
    assert req.lead_rhythm is True
    assert req.dual_guitar is True


def test_isolate_job_request_lead_rhythm_explicit():
    from backend.contracts import IsolateJobCreateRequest

    req = IsolateJobCreateRequest(upload_id="x", lead_rhythm=True)
    assert req.lead_rhythm is True
    assert req.dual_guitar is False


def test_upload_and_job(client, headers):
    midi = Path("eval/fixtures/solo_melody.mid")
    if not midi.exists():
        pytest.skip("fixtures missing")

    wav = midi.parent / "solo_melody.wav"
    if not wav.exists():
        pytest.skip("wav fixture missing")

    with open(wav, "rb") as f:
        upload = client.post(
            "/v1/uploads/audio",
            headers=headers,
            files={"file": ("solo_melody.wav", f, "audio/wav")},
        )
    assert upload.status_code == 200
    upload_id = upload.json()["upload_id"]

    job = client.post(
        "/v1/jobs",
        headers=headers,
        json={"upload_id": upload_id, "separate_stems": False, "max_duration_sec": 15},
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    import time

    status = None
    for _ in range(120):
        status = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.5)

    assert status is not None
    assert status["status"] == "succeeded", status.get("error")
    assert "pdf" in status["artifacts"]
    assert status.get("kind", "tab") == "tab"


def test_isolate_job_mocked(client, headers, monkeypatch):
    from backend.contracts import JobKind

    upload = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
    )
    assert upload.status_code == 200
    upload_id = upload.json()["upload_id"]

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

    job = client.post(
        "/v1/isolate/jobs",
        headers=headers,
        json={"upload_id": upload_id, "model": "htdemucs", "quality": "fast", "max_duration_sec": 15},
    )
    assert job.status_code == 200
    body = job.json()
    assert body["kind"] == JobKind.isolate.value
    job_id = body["id"]

    import time

    status = None
    for _ in range(40):
        status = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)

    assert status is not None
    assert status["status"] == "succeeded", status.get("error")
    assert status["kind"] == "isolate"
    assert "vocals" in status["artifacts"]
    assert "zip" in status["artifacts"]

    bad = client.post(
        "/v1/isolate/jobs",
        headers=headers,
        json={"upload_id": upload_id, "model": "not-real"},
    )
    assert bad.status_code == 400


def test_isolate_job_passes_lead_rhythm_flag(client, headers, monkeypatch):
    from backend.contracts import JobKind

    upload = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
    )
    assert upload.status_code == 200
    upload_id = upload.json()["upload_id"]

    seen_configs: list = []

    def fake_separate_stems(audio_path, output_dir, config=None, on_progress=None):
        seen_configs.append(config)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {}
        for name in ("vocals", "drums", "bass", "other", "guitar", "piano"):
            p = output_dir / f"{name}.wav"
            p.write_bytes(b"stem")
            artifacts[name] = p
        if on_progress:
            on_progress("done", "ok")
        return artifacts

    monkeypatch.setattr("backend.jobs.runner.separate_stems", fake_separate_stems)

    job = client.post(
        "/v1/isolate/jobs",
        headers=headers,
        json={
            "upload_id": upload_id,
            "model": "htdemucs_6s",
            "quality": "fast",
            "lead_rhythm": True,
            "max_duration_sec": 15,
        },
    )
    assert job.status_code == 200
    assert job.json()["kind"] == JobKind.isolate.value
    job_id = job.json()["id"]

    import time

    status = None
    for _ in range(40):
        status = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)

    assert status is not None
    assert status["status"] == "succeeded", status.get("error")
    assert seen_configs and seen_configs[0].lead_rhythm is True

    seen_configs.clear()
    job2 = client.post(
        "/v1/isolate/jobs",
        headers=headers,
        json={
            "upload_id": upload_id,
            "model": "htdemucs_6s",
            "quality": "fast",
            "dual_guitar": True,
            "max_duration_sec": 15,
        },
    )
    assert job2.status_code == 200
    job2_id = job2.json()["id"]
    status2 = None
    for _ in range(40):
        status2 = client.get(f"/v1/jobs/{job2_id}", headers=headers).json()
        if status2["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)
    assert status2 is not None
    assert status2["status"] == "succeeded", status2.get("error")
    assert seen_configs and seen_configs[0].lead_rhythm is True


def test_auth_session_404_when_demo_mode_off(client):
    res = client.post("/v1/auth/session")
    assert res.status_code == 404


def test_auth_session_isolates_anonymous_users(tmp_path, monkeypatch):
    from jose import jwt

    main_mod = configure_backend(
        tmp_path,
        monkeypatch,
        ATT_REQUIRE_AUTH="false",
        ATT_DEMO_MODE="true",
        ATT_SECRET_KEY="dev-test-secret",
    )
    with TestClient(main_mod.app) as client:
        a = client.post("/v1/auth/session")
        b = client.post("/v1/auth/session")
        assert a.status_code == 200, a.text
        assert b.status_code == 200, b.text
        token_a = a.json()["access_token"]
        token_b = b.json()["access_token"]
        assert token_a and token_b
        assert a.json()["email"] != b.json()["email"]

        payload_a = jwt.decode(token_a, "dev-test-secret", algorithms=["HS256"])
        payload_b = jwt.decode(token_b, "dev-test-secret", algorithms=["HS256"])
        assert payload_a["type"] == "access"
        assert payload_b["type"] == "access"
        uid_a = payload_a["sub"]
        uid_b = payload_b["sub"]
        assert uid_a != uid_b

        job = main_mod.job_manager.create_job(user_id=uid_a, upload_id=None, separate_stems=False)
        assert main_mod.job_manager.get_owned(job.id, uid_a) is not None
        assert main_mod.job_manager.get_owned(job.id, uid_b) is None


def test_production_allows_require_auth_false_only_with_demo_mode():
    from pydantic import ValidationError

    from backend.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            env="production",
            secret_key="strong-enough-secret-value",
            cors_origins="https://example.com",
            require_auth=False,
            demo_mode=False,
            bootstrap_admin_password="unique-admin-pass-9x",
        )

    ok = Settings(
        env="production",
        secret_key="strong-enough-secret-value",
        cors_origins="https://example.com",
        require_auth=False,
        demo_mode=True,
        bootstrap_admin_password="unique-admin-pass-9x",
    )
    assert ok.demo_mode is True
    assert ok.require_auth is False
