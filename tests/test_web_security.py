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

from tests.backend_test_utils import configure_backend, fake_wav_bytes


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
        files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
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
        files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
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

    with pytest.raises(ValidationError):
        Settings(
            env="production",
            secret_key="strong-enough-secret-value",
            cors_origins="https://example.com",
            require_auth=False,
            demo_mode=False,
        )

    demo_ok = Settings(
        env="production",
        secret_key="strong-enough-secret-value",
        cors_origins="https://example.com",
        require_auth=False,
        demo_mode=True,
        bootstrap_admin_password="unique-admin-pass-9x",
    )
    assert demo_ok.demo_mode is True

    ok = Settings(
        env="production",
        secret_key="strong-enough-secret-value",
        cors_origins="https://example.com",
        require_auth=True,
        bootstrap_admin_password="unique-admin-pass-9x",
    )
    origins = ok.cors_origin_list()
    assert origins == ["https://example.com"]
    assert "*" not in origins

def test_production_settings_reject_weak_bootstrap_password():
    from backend.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            env="production",
            secret_key="strong-enough-secret-value",
            cors_origins="https://example.com",
            require_auth=True,
            bootstrap_admin_password="changeme",
        )

    with pytest.raises(ValidationError):
        Settings(
            env="production",
            secret_key="strong-enough-secret-value",
            cors_origins="https://example.com",
            require_auth=True,
            bootstrap_admin_password="change-me-now",
        )

    with pytest.raises(ValidationError):
        Settings(
            env="production",
            secret_key="strong-enough-secret-value",
            cors_origins="https://example.com",
            require_auth=True,
            bootstrap_admin_password="short",
        )


def test_demo_mode_unauthenticated_upload_is_401(tmp_path, monkeypatch):
    main_mod = configure_backend(
        tmp_path,
        monkeypatch,
        ATT_REQUIRE_AUTH="false",
        ATT_DEMO_MODE="true",
    )
    with TestClient(main_mod.app) as client:
        res = client.post(
            "/v1/uploads/audio",
            files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
        )
        assert res.status_code == 401

        session = client.post("/v1/auth/session")
        assert session.status_code == 200, session.text
        headers = {"Authorization": f"Bearer {session.json()['access_token']}"}
        ok = client.post(
            "/v1/uploads/audio",
            headers=headers,
            files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
        )
        assert ok.status_code == 200


def test_upload_id_cannot_be_used_by_another_user(auth_env):
    client, _ = auth_env
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    up = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
    )
    assert up.status_code == 200
    upload_id = up.json()["upload_id"]

    from backend.auth import hash_password
    from backend.db import SessionLocal
    from backend.models import User

    db = SessionLocal()
    other = User(
        id=str(uuid.uuid4()),
        email="idor@test.local",
        password_hash=hash_password("otherpass"),
        is_admin=False,
    )
    db.add(other)
    db.commit()
    db.close()

    login2 = client.post(
        "/v1/auth/login",
        json={"email": "idor@test.local", "password": "otherpass"},
    )
    assert login2.status_code == 200, login2.text
    tok2 = login2.json()["access_token"]
    stolen = client.post(
        "/v1/isolate/jobs",
        headers={"Authorization": f"Bearer {tok2}"},
        json={"upload_id": upload_id, "model": "htdemucs", "quality": "fast"},
    )
    assert stolen.status_code == 404


def test_wav_extension_with_non_audio_bytes_rejected(auth_env):
    client, _ = auth_env
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("mix.wav", b"MZ" + b"\x00" * 20, "audio/wav")},
    )
    assert res.status_code == 400
    assert "audio" in res.json()["detail"].lower()


def test_openapi_disabled_in_production(tmp_path, monkeypatch):
    main_mod = configure_backend(
        tmp_path,
        monkeypatch,
        ATT_ENV="production",
        ATT_REQUIRE_AUTH="true",
        ATT_SECRET_KEY="strong-enough-secret-value",
        ATT_BOOTSTRAP_ADMIN_PASSWORD="unique-admin-pass-9x",
        ATT_CORS_ORIGINS="https://example.com",
    )
    with TestClient(main_mod.app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_audio_magic_bytes_unit():
    from backend.limits import is_audio_magic, is_allowed_audio_content

    assert is_audio_magic(fake_wav_bytes())
    assert is_audio_magic(b"fLaC" + b"\x00" * 12)
    assert is_audio_magic(b"ID3" + b"\x00" * 12)
    assert is_audio_magic(b"\x00\x00\x00\x20ftypisom")
    ok, _ = is_allowed_audio_content(b"MZ" + b"\x00" * 20)
    assert ok is False
