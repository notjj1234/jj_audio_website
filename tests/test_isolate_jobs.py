"""Tests for desktop serial isolate jobs."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ui.isolate_jobs import (
    IsolateJobSpec,
    apply_succeeded_job_to_session,
    delete_all_finished_jobs,
    delete_finished_job,
    delete_library_run,
    enqueue_job,
    ensure_worker_started,
    format_job_error,
    job_has_stem_wavs,
    jobs_status_signature,
    jobs_visible_in_queue,
    list_in_flight_jobs,
    list_jobs,
    merge_library_runs,
    queued_wait_caption,
    read_status,
    remove_job,
    write_status,
)


@pytest.fixture()
def jobs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_DATA_DIR", str(tmp_path))
    # Re-bind DATA_DIR used by isolate_jobs
    import ui.common as common
    import ui.isolate_jobs as jobs

    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    return tmp_path


def test_enqueue_persists_queued_status(jobs_dir: Path):
    spec = IsolateJobSpec(
        id="job1",
        audio_path=str(jobs_dir / "a.wav"),
        output_dir=str(jobs_dir / "out"),
        title="Track A",
        created_at=time.time(),
    )
    (jobs_dir / "a.wav").write_bytes(b"x")
    jid = enqueue_job(spec)
    assert jid == "job1"
    status = read_status(jid)
    assert status is not None
    assert status["status"] == "queued"
    assert status["title"] == "Track A"
    rows = list_jobs(limit=5)
    assert any(r["id"] == "job1" for r in rows)


def test_write_status_updates_progress(jobs_dir: Path):
    write_status("j2", status="running", stage="separate", message="Go", progress=0.4)
    status = read_status("j2")
    assert status["status"] == "running"
    assert status["progress"] == 0.4


def test_worker_runs_separate_stems_serially(jobs_dir: Path, monkeypatch):
    """Worker invokes separate_stems and marks job succeeded (mocked engine)."""
    import ui.isolate_jobs as jobs

    audio = jobs_dir / "song.wav"
    audio.write_bytes(b"wav")
    out = jobs_dir / "out"
    out.mkdir()
    calls: list[str] = []

    def fake_separate(*, audio_path, output_dir, config, on_progress):
        calls.append(str(audio_path))
        on_progress("separate", "mock")
        dest = Path(output_dir) / "vocals.wav"
        dest.write_bytes(b"v")
        return {"vocals": dest}

    monkeypatch.setattr(
        "audio_to_tab.isolate.separate_stems",
        fake_separate,
    )
    monkeypatch.setattr(
        "audio_to_tab.hardware.ensure_cuda_available",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "audio_to_tab.hardware.get_desktop_probe",
        lambda: MagicMock(),
    )
    monkeypatch.setattr(
        "ui.media.cleanup_mix_artifacts",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "ui.common.write_run_metadata",
        lambda *_a, **_k: None,
    )

    # Reset worker so a fresh thread picks up our DATA_DIR
    monkeypatch.setattr(jobs, "_WORKER_STARTED", False)
    monkeypatch.setattr(jobs, "_CURRENT_JOB_ID", None)

    spec = IsolateJobSpec(
        id="serial1",
        audio_path=str(audio),
        output_dir=str(out),
        title="Serial",
        created_at=time.time(),
    )
    enqueue_job(spec)
    ensure_worker_started()

    deadline = time.time() + 5
    while time.time() < deadline:
        status = read_status("serial1")
        if status and status.get("status") in ("succeeded", "failed"):
            break
        time.sleep(0.05)

    status = read_status("serial1")
    assert status is not None
    assert status["status"] == "succeeded", status
    assert calls == [str(audio)]
    assert "vocals" in (status.get("artifacts") or {})


def test_remove_job_deletes_queued_folder(jobs_dir: Path):
    spec = IsolateJobSpec(
        id="dropme",
        audio_path=str(jobs_dir / "a.wav"),
        output_dir=str(jobs_dir / "out"),
        title="Drop me",
        created_at=time.time(),
    )
    (jobs_dir / "a.wav").write_bytes(b"x")
    enqueue_job(spec)
    assert (jobs_dir / "isolate_jobs" / "dropme").is_dir()
    assert remove_job("dropme") is True
    assert not (jobs_dir / "isolate_jobs" / "dropme").exists()
    assert all(r["id"] != "dropme" for r in list_jobs())


def test_remove_running_job_marks_cancelled(jobs_dir: Path):
    write_status("run1", status="running", stage="separate", message="Go")
    assert remove_job("run1") is True
    status = read_status("run1")
    assert status is not None
    assert status["status"] == "cancelled"


def test_delete_finished_job_removes_job_and_run_dir(jobs_dir: Path):
    run_dir = jobs_dir / "run_done"
    run_dir.mkdir()
    (run_dir / "vocals.wav").write_bytes(b"x")
    write_status(
        "s1",
        status="succeeded",
        title="Done",
        run_dir=str(run_dir),
        created_at=1.0,
    )
    result = delete_finished_job(
        {"id": "s1", "status": "succeeded", "run_dir": str(run_dir)}
    )
    assert result["ok"] is True
    assert result["run_dir"] == str(run_dir)
    assert not (jobs_dir / "isolate_jobs" / "s1").exists()
    assert not run_dir.exists()


def test_delete_finished_job_skips_running(jobs_dir: Path):
    write_status("r1", status="running", title="Go")
    result = delete_finished_job({"id": "r1", "status": "running"})
    assert result["ok"] is False
    assert read_status("r1")["status"] == "running"


def test_delete_all_finished_jobs_only_succeeded(jobs_dir: Path):
    run_a = jobs_dir / "run_a"
    run_b = jobs_dir / "run_b"
    run_a.mkdir()
    run_b.mkdir()
    write_status("s1", status="succeeded", title="A", run_dir=str(run_a), created_at=1.0)
    write_status("s2", status="succeeded", title="B", run_dir=str(run_b), created_at=2.0)
    write_status("r1", status="running", title="Go", created_at=3.0)
    dirs = delete_all_finished_jobs(list_jobs(limit=10))
    assert set(dirs) == {str(run_a), str(run_b)}
    assert not run_a.exists()
    assert not run_b.exists()
    assert read_status("r1")["status"] == "running"


def test_delete_library_run_removes_job_and_run_dir(jobs_dir: Path):
    run_dir = jobs_dir / "run_lib"
    run_dir.mkdir()
    wav = run_dir / "vocals.wav"
    wav.write_bytes(b"x")
    write_status(
        "s1",
        status="succeeded",
        title="Done",
        run_dir=str(run_dir),
        artifacts={"vocals": str(wav)},
        created_at=1.0,
    )
    assert delete_library_run(str(run_dir)) is True
    assert not (jobs_dir / "isolate_jobs" / "s1").exists()
    assert not run_dir.exists()
    assert all(r["id"] != "s1" for r in list_jobs())


def test_delete_library_run_still_deletes_folder_without_job(jobs_dir: Path):
    run_dir = jobs_dir / "orphan_run"
    run_dir.mkdir()
    (run_dir / "drums.wav").write_bytes(b"x")
    assert delete_library_run(str(run_dir)) is True
    assert not run_dir.exists()


def test_jobs_visible_in_queue_skips_succeeded_without_wavs(jobs_dir: Path):
    gone = jobs_dir / "gone"
    gone.mkdir()
    keep = jobs_dir / "keep"
    keep.mkdir()
    wav = keep / "vocals.wav"
    wav.write_bytes(b"x")
    jobs = [
        {
            "id": "s-gone",
            "status": "succeeded",
            "run_dir": str(gone),
            "artifacts": {"vocals": str(gone / "vocals.wav")},
        },
        {
            "id": "s-keep",
            "status": "succeeded",
            "run_dir": str(keep),
            "artifacts": {"vocals": str(wav)},
        },
        {"id": "q1", "status": "queued"},
    ]
    visible = jobs_visible_in_queue(jobs)
    assert [j["id"] for j in visible] == ["s-keep", "q1"]
    assert job_has_stem_wavs(jobs[0]) is False
    assert job_has_stem_wavs(jobs[1]) is True


def test_jobs_status_signature_changes_when_queued_job_fails():
    queued = [{"id": "c5e7", "status": "queued", "updated_at": 1.0}]
    failed = [{"id": "c5e7", "status": "failed", "updated_at": 2.0}]
    assert jobs_status_signature(queued) != jobs_status_signature(failed)
    assert jobs_status_signature(failed) == jobs_status_signature(failed)


def test_list_in_flight_jobs_excludes_succeeded(jobs_dir: Path):
    write_status("q1", status="queued", title="Wait", created_at=1.0)
    write_status("r1", status="running", title="Go", created_at=2.0)
    write_status("f1", status="failed", title="Nope", created_at=3.0)
    write_status("s1", status="succeeded", title="Done", created_at=4.0)
    ids = {row["id"] for row in list_in_flight_jobs()}
    assert ids == {"q1", "r1", "f1"}


def test_queued_wait_caption_is_position_not_percent():
    queued = ["a", "b", "c"]
    assert queued_wait_caption("b", queued) == "Waiting — position 2 of 3"
    assert "%" not in queued_wait_caption("a", queued)


def test_merge_library_runs_dedupes_by_run_dir():
    recent = [
        {"run_dir": "/runs/one", "title": "From recent", "created_at": 10.0, "artifacts": {"vocals": "/runs/one/vocals.wav"}},
    ]
    jobs = [
        {
            "id": "job1",
            "status": "succeeded",
            "run_dir": "/runs/one",
            "title": "From job",
            "created_at": 11.0,
            "artifacts": {"vocals": "/runs/one/vocals.wav"},
        },
        {
            "id": "job2",
            "status": "succeeded",
            "run_dir": "/runs/two",
            "title": "Other",
            "created_at": 12.0,
            "artifacts": {"drums": "/runs/two/drums.wav"},
        },
    ]
    merged = merge_library_runs(recent, jobs)
    dirs = [row["run_dir"] for row in merged]
    assert dirs == ["/runs/two", "/runs/one"]
    assert merged[1]["title"] == "From recent"


def test_apply_succeeded_job_to_session_sets_viewing_and_keeps_source(tmp_path: Path):
    wav = tmp_path / "vocals.wav"
    wav.write_bytes(b"RIFF")
    session: dict = {"isolate_source_audio_path": "keep-me.wav"}
    ok = apply_succeeded_job_to_session(
        session,
        {
            "id": "job9",
            "status": "succeeded",
            "title": "Clip",
            "run_dir": str(tmp_path),
            "artifacts": {"vocals": str(wav)},
            "source_audio_path": str(tmp_path / "song.wav"),
            "source_fingerprint": "fp1",
            "region_label": "0:10–0:40",
            "clip_length": 30.0,
            "custom_stems": [],
        },
        viewing_mode="latest",
    )
    assert ok is True
    assert session["isolate_source_audio_path"] == str(tmp_path / "song.wav")
    assert session["isolate_viewing_job_id"] == "latest"
    assert session["isolate_viewing_run_dir"] == str(tmp_path)
    assert session["isolate_region_label"] == "0:10–0:40"
    assert session["isolate_clip_length"] == 30.0
    assert session["isolate_results_fp"]
    assert session["isolate_source_kind"] == "file"
    assert "isolate_volumes_db" not in session


def test_apply_succeeded_job_to_session_fills_empty_session(tmp_path: Path):
    wav = tmp_path / "vocals.wav"
    wav.write_bytes(b"RIFF")
    session: dict = {}
    assert apply_succeeded_job_to_session(
        session,
        {
            "id": "job-empty",
            "status": "succeeded",
            "title": "Latest",
            "run_dir": str(tmp_path),
            "artifacts": {"vocals": str(wav)},
        },
        viewing_mode="latest",
    )
    assert session["isolate_artifacts"]["vocals"] == str(wav)
    assert session["isolate_viewing_run_dir"] == str(tmp_path)
    assert session["isolate_viewing_job_id"] == "latest"


def test_apply_succeeded_job_to_session_infers_youtube_kind(tmp_path: Path):
    wav = tmp_path / "vocals.wav"
    wav.write_bytes(b"RIFF")
    session: dict = {}
    ok = apply_succeeded_job_to_session(
        session,
        {
            "id": "yt1",
            "status": "succeeded",
            "title": "Party",
            "run_dir": str(tmp_path),
            "artifacts": {"vocals": str(wav)},
            "source_fingerprint": "youtube:https://youtu.be/abc",
        },
        viewing_mode="latest",
    )
    assert ok is True
    assert session["isolate_source_kind"] == "youtube"


def test_enqueue_persists_source_kind(jobs_dir: Path):
    spec = IsolateJobSpec(
        id="ytjob",
        audio_path=str(jobs_dir / "a.wav"),
        output_dir=str(jobs_dir / "out"),
        title="Party",
        created_at=time.time(),
        source_kind="youtube",
        source_fingerprint="youtube:https://youtu.be/abc",
    )
    (jobs_dir / "a.wav").write_bytes(b"x")
    enqueue_job(spec)
    status = read_status("ytjob")
    assert status is not None
    assert status["source_kind"] == "youtube"
    assert status["source_fingerprint"] == "youtube:https://youtu.be/abc"
    rows = list_jobs(limit=5)
    match = next(r for r in rows if r["id"] == "ytjob")
    assert match["source_kind"] == "youtube"


def test_apply_succeeded_job_to_session_pins_when_requested(tmp_path: Path):
    wav = tmp_path / "drums.wav"
    wav.write_bytes(b"RIFF")
    session: dict = {}
    apply_succeeded_job_to_session(
        session,
        {
            "id": "old",
            "status": "succeeded",
            "title": "Old",
            "run_dir": str(tmp_path),
            "artifacts": {"drums": str(wav)},
        },
        viewing_mode="old",
    )
    assert session["isolate_viewing_job_id"] == "old"


def test_apply_succeeded_job_to_session_missing_wavs_returns_false(tmp_path: Path):
    session: dict = {"isolate_artifacts": {"keep": "x"}}
    ok = apply_succeeded_job_to_session(
        session,
        {
            "id": "gone",
            "status": "succeeded",
            "title": "Gone",
            "run_dir": str(tmp_path),
            "artifacts": {"vocals": str(tmp_path / "missing.wav")},
        },
    )
    assert ok is False
    assert session["isolate_artifacts"] == {"keep": "x"}


def test_worker_persists_eta_fields(jobs_dir: Path, monkeypatch):
    """Worker writes audio_duration_sec / stages / job_estimate_sec before finishing."""
    import ui.isolate_jobs as jobs

    audio = jobs_dir / "song.wav"
    audio.write_bytes(b"wav")
    out = jobs_dir / "out"
    out.mkdir()

    def fake_separate(*, audio_path, output_dir, config, on_progress):
        on_progress("separate", "mock")
        dest = Path(output_dir) / "vocals.wav"
        dest.write_bytes(b"v")
        return {"vocals": dest}

    monkeypatch.setattr("audio_to_tab.isolate.separate_stems", fake_separate)
    monkeypatch.setattr("audio_to_tab.hardware.ensure_cuda_available", lambda *a, **k: None)
    monkeypatch.setattr("audio_to_tab.hardware.get_desktop_probe", lambda: MagicMock())
    monkeypatch.setattr("ui.media.cleanup_mix_artifacts", lambda *_a, **_k: None)
    monkeypatch.setattr("ui.common.write_run_metadata", lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, "_WORKER_STARTED", False)
    monkeypatch.setattr(jobs, "_CURRENT_JOB_ID", None)
    monkeypatch.setattr(jobs, "_WORKER_THREAD", None)

    spec = IsolateJobSpec(
        id="eta1",
        audio_path=str(audio),
        output_dir=str(out),
        title="Eta",
        audio_duration_sec=90.0,
        created_at=time.time(),
    )
    enqueue_job(spec)
    ensure_worker_started()
    deadline = time.time() + 5
    while time.time() < deadline:
        status = read_status("eta1")
        if status and status.get("status") in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    status = read_status("eta1")
    assert status is not None
    assert status["status"] == "succeeded", status.get("error") or status.get("traceback") or status
    assert status.get("audio_duration_sec") == 90.0
    assert status.get("stages")
    assert status.get("job_estimate_sec")


def test_format_job_error_keeps_demucs_segment_message():
    raw = (
        "Demucs failed: Warning: You are sending unauthenticated requests to the HF Hub. "
        "Please set a HF_TOKEN to enable higher rate limits and faster downloads.\n"
        "Cannot use a Transformer model with a longer segment than it was trained for. "
        "Maximum segment is: 7.8\n"
    )
    cleaned = format_job_error(raw)
    assert "HF_TOKEN" not in cleaned
    assert "unauthenticated" not in cleaned
    assert "Maximum segment is: 7.8" in cleaned


def test_format_job_error_is_one_short_sentence_without_app_paths():
    raw = (
        "guitar-ft unavailable (RuntimeError: Could not load libtorchcodec "
        "from /Applications/AudioTools.app/Contents/Frameworks/libavutil.59.dylib "
        "because FFmpeg 7 is missing); using stock htdemucs_6s\n"
        + ("x" * 400)
    )
    cleaned = format_job_error(raw)
    assert "/Applications/AudioTools.app" not in cleaned
    assert "libavutil" not in cleaned
    assert len(cleaned) <= 160
    assert cleaned
