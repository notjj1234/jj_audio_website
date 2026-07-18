"""Auth, upload limits, CORS, and job persistence tests."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

pytest.importorskip("fastapi")
pytest.importorskip("jose")
pytest.importorskip("sqlalchemy")

from tests.backend_test_utils import configure_backend


@pytest.fixture()
def auth_env(tmp_path, monkeypatch):
    main_mod = configure_backend(
        tmp_path,
        monkeypatch,
        ATT_REQUIRE_AUTH="true",
        ATT_SECRET_KEY="test-secret-key-not-for-prod",
        ATT_BOOTSTRAP_ADMIN_EMAIL="admin@test.local",
        ATT_BOOTSTRAP_ADMIN_PASSWORD="testpass123",
        ATT_MAX_UPLOAD_MB="1",
        ATT_ALLOW_YOUTUBE="false",
    )
    with TestClient(main_mod.app) as client:
        yield client, main_mod


def _login(client: TestClient) -> str:
    res = client.post(
        "/v1/auth/login",
        json={"email": "admin@test.local", "password": "testpass123"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_unauthenticated_upload_401(auth_env):
    client, _ = auth_env
    res = client.post(
        "/v1/uploads/audio",
        files={"file": ("x.wav", b"RIFF", "audio/wav")},
    )
    assert res.status_code == 401


def test_login_and_owner_artifacts(auth_env, monkeypatch):
    client, _ = auth_env
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    up = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("mix.wav", b"fake-audio-bytes", "audio/wav")},
    )
    assert up.status_code == 200
    upload_id = up.json()["upload_id"]

    def fake_separate_stems(audio_path, output_dir, config=None, on_progress=None):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        p = output_dir / "vocals.wav"
        p.write_bytes(b"stem")
        if on_progress:
            on_progress("done", "ok")
        return {"vocals": p}

    monkeypatch.setattr("backend.jobs.runner.separate_stems", fake_separate_stems)

    job = client.post(
        "/v1/isolate/jobs",
        headers=headers,
        json={"upload_id": upload_id, "model": "htdemucs", "quality": "fast"},
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    import time

    status = None
    for _ in range(40):
        status = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)
    assert status is not None
    assert status["status"] == "succeeded"
    assert "vocals" in status["artifacts"]
    assert "/signed?" in status["artifacts"]["vocals"]

    signed = status["artifacts"]["vocals"]
    dl = client.get(signed)
    assert dl.status_code == 200

    from backend.auth import hash_password
    from backend.db import SessionLocal
    from backend.models import User

    db = SessionLocal()
    other = User(
        id=str(uuid.uuid4()),
        email="other@test.local",
        password_hash=hash_password("otherpass"),
        is_admin=False,
    )
    db.add(other)
    db.commit()
    db.close()

    login2 = client.post(
        "/v1/auth/login",
        json={"email": "other@test.local", "password": "otherpass"},
    )
    tok2 = login2.json()["access_token"]
    denied = client.get(f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {tok2}"})
    assert denied.status_code == 404


def test_upload_oversize_and_bad_mime(auth_env):
    client, _ = auth_env
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    big = b"x" * (2 * 1024 * 1024)
    over = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("big.wav", big, "audio/wav")},
    )
    assert over.status_code == 413

    bad = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("notes.exe", b"MZ", "application/x-msdownload")},
    )
    assert bad.status_code == 400


def test_youtube_disabled(auth_env):
    client, _ = auth_env
    token = _login(client)
    res = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert res.status_code == 403


def test_job_persists_across_manager_recreate(auth_env):
    client, main_mod = auth_env
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    up = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("mix.wav", b"fake", "audio/wav")},
    )
    upload_id = up.json()["upload_id"]
    user_id = client.get("/v1/auth/me", headers=headers).json()["id"]

    job = main_mod.job_manager.create_isolate_job(
        user_id=user_id,
        upload_id=upload_id,
        model="htdemucs",
        quality="fast",
    )
    job_id = job.id

    from backend.jobs.manager import JobManager

    restarted = JobManager(main_mod.data_dir)
    loaded = restarted.get(job_id)
    assert loaded is not None
    assert loaded.id == job_id
    assert loaded.kind.value == "isolate"


def test_production_settings_reject_star_cors_and_weak_secret():
    from backend.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            env="production",
            secret_key="dev-only-change-me",
            cors_origins="https://example.com",
            require_auth=True,
        )

    with pytest.raises(ValidationError):
        Settings(
            env="production",
            secret_key="strong-enough-secret-value",
            cors_origins="*",
            require_auth=True,
        )

    with pytest.raises(ValidationError):
        Settings(
            env="production",
            secret_key="strong-enough-secret-value",
            cors_origins="https://example.com",
            require_auth=False,
        )

    ok = Settings(
        env="production",
        secret_key="strong-enough-secret-value",
        cors_origins="https://example.com",
        require_auth=True,
    )
    origins = ok.cors_origin_list()
    assert origins == ["https://example.com"]
    assert "*" not in origins
