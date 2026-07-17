"""API smoke tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

from backend.main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    res = client.get("/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_isolate_job_request_defaults_to_full_song():
    from backend.contracts import IsolateJobCreateRequest

    req = IsolateJobCreateRequest(upload_id="x")
    assert req.max_duration_sec is None
    assert req.lead_rhythm is False
    assert req.dual_guitar is False


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


def test_upload_and_job(client, tmp_path, monkeypatch):
    midi = Path("eval/fixtures/solo_melody.mid")
    if not midi.exists():
        pytest.skip("fixtures missing")

    # Patch data dir for test isolation
    from backend import main as main_mod

    monkeypatch.setattr(main_mod, "data_dir", tmp_path)
    monkeypatch.setattr(main_mod.job_manager, "data_dir", tmp_path)
    monkeypatch.setattr(main_mod.job_manager, "uploads_dir", tmp_path / "uploads")
    monkeypatch.setattr(main_mod.job_manager, "jobs_dir", tmp_path / "jobs")
    main_mod.job_manager.uploads_dir.mkdir(parents=True, exist_ok=True)
    main_mod.job_manager.jobs_dir.mkdir(parents=True, exist_ok=True)

    with open(midi.parent / "solo_melody.wav", "rb") as f:
        upload = client.post(
            "/v1/uploads/audio",
            files={"file": ("solo_melody.wav", f, "audio/wav")},
        )
    assert upload.status_code == 200
    upload_id = upload.json()["upload_id"]

    job = client.post(
        "/v1/jobs",
        json={"upload_id": upload_id, "separate_stems": False, "max_duration_sec": 15},
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    import time

    for _ in range(120):
        status = client.get(f"/v1/jobs/{job_id}").json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.5)

    assert status["status"] == "succeeded", status.get("error")
    assert "pdf" in status["artifacts"]
    assert status.get("kind", "tab") == "tab"


def test_isolate_job_mocked(client, tmp_path, monkeypatch):
    from backend import main as main_mod
    from backend.contracts import JobKind

    monkeypatch.setattr(main_mod, "data_dir", tmp_path)
    monkeypatch.setattr(main_mod.job_manager, "data_dir", tmp_path)
    monkeypatch.setattr(main_mod.job_manager, "uploads_dir", tmp_path / "uploads")
    monkeypatch.setattr(main_mod.job_manager, "jobs_dir", tmp_path / "jobs")
    main_mod.job_manager.uploads_dir.mkdir(parents=True, exist_ok=True)
    main_mod.job_manager.jobs_dir.mkdir(parents=True, exist_ok=True)

    upload = client.post(
        "/v1/uploads/audio",
        files={"file": ("mix.wav", b"fake-audio", "audio/wav")},
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
        json={"upload_id": upload_id, "model": "htdemucs", "quality": "fast", "max_duration_sec": 15},
    )
    assert job.status_code == 200
    body = job.json()
    assert body["kind"] == JobKind.isolate.value
    job_id = body["id"]

    import time

    for _ in range(40):
        status = client.get(f"/v1/jobs/{job_id}").json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)

    assert status["status"] == "succeeded", status.get("error")
    assert status["kind"] == "isolate"
    assert "vocals" in status["artifacts"]
    assert "zip" in status["artifacts"]

    bad = client.post(
        "/v1/isolate/jobs",
        json={"upload_id": upload_id, "model": "not-real"},
    )
    assert bad.status_code == 400


def test_isolate_job_passes_lead_rhythm_flag(client, tmp_path, monkeypatch):
    from backend import main as main_mod
    from backend.contracts import JobKind

    monkeypatch.setattr(main_mod, "data_dir", tmp_path)
    monkeypatch.setattr(main_mod.job_manager, "data_dir", tmp_path)
    monkeypatch.setattr(main_mod.job_manager, "uploads_dir", tmp_path / "uploads")
    monkeypatch.setattr(main_mod.job_manager, "jobs_dir", tmp_path / "jobs")
    main_mod.job_manager.uploads_dir.mkdir(parents=True, exist_ok=True)
    main_mod.job_manager.jobs_dir.mkdir(parents=True, exist_ok=True)

    upload = client.post(
        "/v1/uploads/audio",
        files={"file": ("mix.wav", b"fake-audio", "audio/wav")},
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

    for _ in range(40):
        status = client.get(f"/v1/jobs/{job_id}").json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)

    assert status["status"] == "succeeded", status.get("error")
    assert seen_configs and seen_configs[0].lead_rhythm is True

    # dual_guitar alias also enables lead_rhythm on the runner config
    seen_configs.clear()
    job2 = client.post(
        "/v1/isolate/jobs",
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
    for _ in range(40):
        status2 = client.get(f"/v1/jobs/{job2_id}").json()
        if status2["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)
    assert status2["status"] == "succeeded", status2.get("error")
    assert seen_configs and seen_configs[0].lead_rhythm is True
