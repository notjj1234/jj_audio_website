"""Single-flight job gate tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

from tests.backend_test_utils import configure_backend, fake_wav_bytes, login_headers


@pytest.fixture()
def single_flight_client(tmp_path, monkeypatch):
    main_mod = configure_backend(
        tmp_path,
        monkeypatch,
        ATT_REQUIRE_AUTH="false",
        ATT_DEMO_MODE="true",
        ATT_SINGLE_FLIGHT_JOBS="true",
        ATT_MAX_JOB_DURATION_SEC="90",
    )
    from backend.jobs import single_flight

    single_flight.release()
    with TestClient(main_mod.app) as client:
        yield client, main_mod, single_flight
    single_flight.release()


def test_isolate_job_create_succeeds_while_runner_slot_held(single_flight_client, monkeypatch):
    """Create enqueues with HTTP 200 even when the Demucs slot is held.

    Isolate create no longer 503s on busy; the runner waits for the slot.
    """
    client, main_mod, single_flight = single_flight_client
    headers = login_headers(client)

    upload = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
    )
    assert upload.status_code == 200
    upload_id = upload.json()["upload_id"]

    assert single_flight.try_acquire()

    async def noop_enqueue(*_args, **_kwargs):
        return None

    monkeypatch.setattr(main_mod, "_enqueue_or_run", noop_enqueue)

    created = client.post(
        "/v1/isolate/jobs",
        headers=headers,
        json={"upload_id": upload_id, "model": "htdemucs", "quality": "fast", "max_duration_sec": 15},
    )
    assert created.status_code == 200, created.text
    single_flight.release()


def test_single_flight_disabled_allows_concurrent_create(tmp_path, monkeypatch):
    main_mod = configure_backend(
        tmp_path,
        monkeypatch,
        ATT_REQUIRE_AUTH="false",
        ATT_SINGLE_FLIGHT_JOBS="false",
    )
    from backend.jobs import single_flight

    single_flight.release()
    # Simulate a held slot; with feature off, creates must still succeed
    assert single_flight.try_acquire()

    async def noop_enqueue(*_args, **_kwargs):
        return None

    monkeypatch.setattr(main_mod, "_enqueue_or_run", noop_enqueue)

    with TestClient(main_mod.app) as client:
        headers = login_headers(client)
        upload = client.post(
            "/v1/uploads/audio",
            headers=headers,
            files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
        )
        assert upload.status_code == 200
        res = client.post(
            "/v1/isolate/jobs",
            headers=headers,
            json={
                "upload_id": upload.json()["upload_id"],
                "model": "htdemucs",
                "quality": "fast",
                "max_duration_sec": 15,
            },
        )
        assert res.status_code == 200, res.text

    single_flight.release()
