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


def test_second_isolate_job_returns_503_while_slot_held(single_flight_client, monkeypatch):
    client, main_mod, single_flight = single_flight_client
    headers = login_headers(client)

    upload = client.post(
        "/v1/uploads/audio",
        headers=headers,
        files={"file": ("mix.wav", fake_wav_bytes(), "audio/wav")},
    )
    assert upload.status_code == 200
    upload_id = upload.json()["upload_id"]

    # Hold the slot as if a job were running
    assert single_flight.try_acquire()

    blocked = client.post(
        "/v1/isolate/jobs",
        headers=headers,
        json={"upload_id": upload_id, "model": "htdemucs", "quality": "fast", "max_duration_sec": 15},
    )
    assert blocked.status_code == 503
    assert "one job" in blocked.json()["detail"].lower() or "already running" in blocked.json()["detail"].lower()

    single_flight.release()

    def fake_separate_stems(audio_path, output_dir, config=None, on_progress=None):
        from pathlib import Path

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

    ok = client.post(
        "/v1/isolate/jobs",
        headers=headers,
        json={"upload_id": upload_id, "model": "htdemucs", "quality": "fast", "max_duration_sec": 15},
    )
    assert ok.status_code == 200, ok.text


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

    def fake_separate_stems(audio_path, output_dir, config=None, on_progress=None):
        from pathlib import Path

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {}
        for name in ("vocals", "drums", "bass", "other"):
            p = output_dir / f"{name}.wav"
            p.write_bytes(b"stem")
            artifacts[name] = p
        return artifacts

    monkeypatch.setattr("backend.jobs.runner.separate_stems", fake_separate_stems)

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
