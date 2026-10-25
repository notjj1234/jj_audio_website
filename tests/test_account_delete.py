"""Account / data deletion (compliance C20)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.account import delete_user_account
from backend.auth import hash_password
from backend.models import Job, JobArtifact, JobKindDB, JobStatusDB, Upload, User
from backend.storage import LocalStorage, reset_storage
from tests.backend_test_utils import configure_backend


def test_delete_user_account_removes_db_and_storage(tmp_path: Path):
    storage = LocalStorage(tmp_path / "storage")
    engine_dir = tmp_path / "acct"
    engine_dir.mkdir()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.db import Base
    import backend.models  # noqa: F401

    engine = create_engine(
        f"sqlite:///{engine_dir / 't.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        user = User(
            id="u-del-1",
            email="del@example.com",
            password_hash=hash_password("x"),
            is_admin=False,
            is_anonymous=False,
        )
        db.add(user)
        up_key = "uploads/u-del-1/a.wav"
        storage.put_bytes(up_key, b"RIFF")
        db.add(
            Upload(
                id="up-1",
                user_id=user.id,
                storage_key=up_key,
                filename="a.wav",
            )
        )
        job = Job(
            id="j-1",
            user_id=user.id,
            kind=JobKindDB.isolate,
            status=JobStatusDB.succeeded,
        )
        db.add(job)
        art_key = "jobs/j-1/guitar.wav"
        storage.put_bytes(art_key, b"wav")
        db.add(
            JobArtifact(
                job_id=job.id,
                kind="guitar",
                storage_key=art_key,
                filename="guitar.wav",
            )
        )
        db.commit()

        counts = delete_user_account(db, user, storage)
        assert counts["deleted_jobs"] == 1
        assert counts["deleted_uploads"] == 1
        assert counts["deleted_artifacts"] >= 1
        assert db.get(User, "u-del-1") is None
        assert not storage.exists(up_key)
        assert not storage.exists(art_key)
    finally:
        db.close()


def test_delete_me_endpoint_for_anonymous(tmp_path, monkeypatch):
    main_mod = configure_backend(
        tmp_path,
        monkeypatch,
        ATT_REQUIRE_AUTH="false",
        ATT_DEMO_MODE="true",
    )
    with TestClient(main_mod.app) as client:
        session = client.post("/v1/auth/session")
        assert session.status_code == 200, session.text
        token = session.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        me = client.get("/v1/auth/me", headers=headers)
        assert me.status_code == 200
        uid = me.json()["id"]

        res = client.delete("/v1/auth/me", headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "deleted"

        gone = client.get("/v1/auth/me", headers=headers)
        assert gone.status_code in (401, 403)

        from backend.db import SessionLocal

        db = SessionLocal()
        try:
            assert db.get(User, uid) is None
        finally:
            db.close()
    reset_storage()


def test_delete_me_rejects_bootstrap_admin(tmp_path, monkeypatch):
    main_mod = configure_backend(
        tmp_path,
        monkeypatch,
        ATT_REQUIRE_AUTH="true",
        ATT_DEMO_MODE="false",
    )
    with TestClient(main_mod.app) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@localhost", "password": "changeme"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        res = client.delete("/v1/auth/me", headers=headers)
        assert res.status_code == 400
    reset_storage()
