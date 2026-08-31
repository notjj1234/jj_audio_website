"""Serial desktop isolate jobs — process-level worker, progress on disk.

Demucs stays off the Streamlit request thread so page switches do not abort a run.
Only one job runs at a time (8–16 GB RAM).
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import re
import shutil
import threading
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from ui.common import DATA_DIR, delete_run

_JOBS_SUBDIR = "isolate_jobs"
_QUEUE_LOCK = threading.Lock()
_WORKER_STARTED = False
_WORKER_LOCK = threading.Lock()
_WORKER_THREAD: threading.Thread | None = None
_ACTIVE_JOB_ID: str | None = None
_ACTIVE_PROCESS: multiprocessing.Process | None = None


@dataclass
class IsolateJobSpec:
    """Serializable job request for desktop isolate."""

    id: str
    audio_path: str
    output_dir: str
    title: str
    model: str = "htdemucs_6s"
    quality: str = "fast"
    device: str = "cpu"
    start_sec: float = 0.0
    max_duration_sec: float | None = None
    two_stems: str | None = None
    guitar_checkpoint: str | None = None
    two_pass: bool = False
    guitar_refine: bool = False
    emit_stems: list[str] | None = None
    fold_other_into_guitar: bool = True
    fold_other_mode: str = "best_effort"
    custom_stems: list[str] = field(default_factory=list)
    track_options: list[str] = field(default_factory=list)
    source_fingerprint: str | None = None
    source_kind: str | None = None
    region_label: str | None = None
    owner: str | None = None
    created_at: float = 0.0
    audio_duration_sec: float | None = None
    prior_timing: dict[str, Any] | None = None
    low_end_restore_db: float = 0.0
    sub_bass_debleed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IsolateJobSpec:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        raw_emit = filtered.get("emit_stems")
        if raw_emit is not None:
            filtered["emit_stems"] = list(raw_emit)
        return cls(**filtered)


def jobs_root() -> Path:
    root = DATA_DIR / _JOBS_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _job_dir(job_id: str) -> Path:
    path = jobs_root() / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _spec_path(job_id: str) -> Path:
    return _job_dir(job_id) / "spec.json"


def _status_path(job_id: str) -> Path:
    return _job_dir(job_id) / "status.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    last_exc: OSError | None = None
    for attempt in range(8):
        try:
            tmp.replace(path)
            return
        except OSError as exc:
            last_exc = exc
            time.sleep(0.02 * (attempt + 1))
    if last_exc is not None:
        raise last_exc


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _default_status(job_id: str) -> dict[str, Any]:
    return {
        "id": job_id,
        "status": "queued",
        "stage": "pending",
        "message": "Queued",
        "progress": 0.0,
        "error": None,
        "artifacts": {},
        "updated_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "completed_stages": [],
        "pause_requested_at": None,
        "paused_at": None,
    }


def jobs_status_signature(jobs: list[dict[str, Any]]) -> tuple[tuple[str, str], ...]:
    """Stable id+status snapshot so the UI can detect queue changes between polls."""
    return tuple((str(job.get("id") or ""), str(job.get("status") or "")) for job in jobs)


_ABS_PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\|/(?:Users|home|Applications|opt|usr|Library|private)/)\S+"
)
_ERROR_MAX_CHARS = 160


def format_job_error(error: str | None) -> str:
    """One short user-facing sentence. Drop HF hub noise and filesystem paths."""
    text = (error or "").strip()
    if not text:
        return "Separation failed"
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "HF_TOKEN" in line or "unauthenticated requests to the HF Hub" in line:
            continue
        cleaned_lines.append(line)
    cleaned = " ".join(cleaned_lines).strip() or text
    cleaned = _ABS_PATH_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :;-")
    if len(cleaned) > _ERROR_MAX_CHARS:
        cleaned = cleaned[: _ERROR_MAX_CHARS - 1].rstrip() + "…"
    return cleaned or "Separation failed"


def write_status(job_id: str, **updates: Any) -> dict[str, Any]:
    path = _status_path(job_id)
    current = _read_json(path) or _default_status(job_id)
    current.update(updates)
    current["id"] = job_id
    current["updated_at"] = time.time()
    _write_json(path, current)
    return current


def read_status(job_id: str) -> dict[str, Any] | None:
    return _read_json(_status_path(job_id))


def read_spec(job_id: str) -> IsolateJobSpec | None:
    data = _read_json(_spec_path(job_id))
    if not data:
        return None
    try:
        return IsolateJobSpec.from_dict(data)
    except Exception:
        return None


def enqueue_job(spec: IsolateJobSpec) -> str:
    """Persist a queued job and ensure the serial worker is running."""
    if not spec.id:
        spec.id = uuid.uuid4().hex
    if not spec.created_at:
        spec.created_at = time.time()
    _write_json(_spec_path(spec.id), spec.to_dict())
    write_status(
        spec.id,
        status="queued",
        stage="pending",
        message="Queued",
        progress=0.0,
        error=None,
        artifacts={},
        title=spec.title,
        created_at=spec.created_at,
        source_kind=spec.source_kind,
        source_fingerprint=spec.source_fingerprint,
    )
    ensure_worker_started()
    return spec.id


def _abort_flag_path(job_id: str) -> Path:
    return _job_dir(job_id) / "abort.flag"


def _checkpoint_dir(job_id: str) -> Path:
    return _job_dir(job_id) / "checkpoint"


def _request_abort(job_id: str) -> None:
    _abort_flag_path(job_id).write_text("1", encoding="utf-8")


def _clear_abort_flag(job_id: str) -> None:
    _abort_flag_path(job_id).unlink(missing_ok=True)


def _terminate_active_process(job_id: str) -> None:
    with _QUEUE_LOCK:
        proc = _ACTIVE_PROCESS
        active_id = _ACTIVE_JOB_ID
    if proc is None or active_id != job_id:
        return
    if not proc.is_alive():
        return
    proc.terminate()
    proc.join(timeout=5.0)
    if proc.is_alive():
        proc.kill()
        proc.join(timeout=2.0)


def _delete_job_folder(job_id: str) -> bool:
    path = jobs_root() / job_id
    if not path.is_dir():
        return False
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


def _finalize_job_after_process(job_id: str) -> None:
    """Apply pause/cancel cleanup after the child process exits."""
    status = read_status(job_id)
    if not status:
        return
    st = status.get("status")
    if st == "pausing":
        write_status(
            job_id,
            status="paused",
            message="Paused",
            paused_at=time.time(),
        )
        _clear_abort_flag(job_id)
    elif st == "cancelled":
        _delete_job_folder(job_id)
    elif st == "running":
        write_status(
            job_id,
            status="failed",
            stage="error",
            message="Separation stopped unexpectedly",
            error="Process exited before completion",
            finished_at=time.time(),
        )


def pause_job(job_id: str) -> bool:
    """Pause a running job: abort between stages and keep checkpoints on disk."""
    if not job_id or "/" in job_id or "\\" in job_id or job_id in {".", ".."}:
        return False
    status = read_status(job_id)
    if not status or status.get("status") != "running":
        return False
    _request_abort(job_id)
    write_status(
        job_id,
        status="pausing",
        message="Pausing…",
        pause_requested_at=time.time(),
    )
    _terminate_active_process(job_id)
    ensure_worker_started()
    return True


def resume_job(job_id: str) -> bool:
    """Re-queue a paused job so it continues from the last saved stage."""
    if not job_id or "/" in job_id or "\\" in job_id or job_id in {".", ".."}:
        return False
    status = read_status(job_id)
    if not status or status.get("status") != "paused":
        return False
    if read_spec(job_id) is None:
        return False
    _clear_abort_flag(job_id)
    write_status(
        job_id,
        status="queued",
        stage="pending",
        message="Queued",
        progress=float(status.get("progress") or 0.0),
        error=None,
        pause_requested_at=None,
        paused_at=status.get("paused_at"),
    )
    ensure_worker_started()
    return True


def remove_job(job_id: str) -> bool:
    """Drop a job from the list (queued / paused / failed / done).

    Running jobs are cancelled, their worker process is terminated, and the
    folder is removed once the process exits.
    """
    if not job_id or "/" in job_id or "\\" in job_id or job_id in {".", ".."}:
        return False
    status = read_status(job_id)
    if status and status.get("status") in {"running", "pausing"}:
        _request_abort(job_id)
        write_status(
            job_id,
            status="cancelled",
            stage="error",
            message="Removed from queue",
            error="Removed from queue",
            finished_at=time.time(),
        )
        _terminate_active_process(job_id)
        ensure_worker_started()
        return True
    return _delete_job_folder(job_id)


def delete_finished_job(job: dict[str, Any]) -> dict[str, Any]:
    """Remove a succeeded job record and its run directory (stems on disk)."""
    if job.get("status") != "succeeded":
        return {"ok": False, "run_dir": None}
    job_id = str(job.get("id") or "")
    run_dir = str(job.get("run_dir") or "") or None
    removed = bool(job_id) and remove_job(job_id)
    deleted_run = bool(run_dir) and delete_run(run_dir)
    return {"ok": bool(removed or deleted_run), "run_dir": run_dir}


def delete_all_finished_jobs(jobs: list[dict[str, Any]]) -> list[str]:
    """Delete every succeeded job. Returns run_dirs that were targeted."""
    dirs: list[str] = []
    for job in jobs:
        if job.get("status") != "succeeded":
            continue
        result = delete_finished_job(job)
        run_dir = result.get("run_dir")
        if run_dir:
            dirs.append(str(run_dir))
    return dirs


def job_has_stem_wavs(job: dict[str, Any]) -> bool:
    """True when a job still has at least one stem wav on disk."""
    for path in (job.get("artifacts") or {}).values():
        wav = Path(str(path))
        if wav.suffix.lower() == ".wav" and wav.is_file():
            return True
    run_dir = job.get("run_dir")
    if run_dir:
        folder = Path(str(run_dir))
        if folder.is_dir():
            return any(p.is_file() and p.suffix.lower() == ".wav" for p in folder.iterdir())
    return False


def jobs_visible_in_queue(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop succeeded jobs whose wavs are gone (run deleted outside Queue)."""
    visible: list[dict[str, Any]] = []
    for job in jobs:
        if job.get("status") == "succeeded" and not job_has_stem_wavs(job):
            continue
        visible.append(job)
    return visible


def delete_library_run(run_dir: str) -> bool:
    """Remove a mixer run and every succeeded queue job that points at it."""
    wanted = str(run_dir or "")
    if not wanted:
        return False
    ok = False
    for job in list_jobs(limit=50):
        if job.get("status") != "succeeded":
            continue
        if str(job.get("run_dir") or "") != wanted:
            continue
        result = delete_finished_job(job)
        ok = ok or bool(result.get("ok"))
    ok = bool(delete_run(wanted)) or ok
    return ok


def list_jobs(*, limit: int = 20) -> list[dict[str, Any]]:
    """Newest-first job status rows (queued / running / done / failed)."""
    root = jobs_root()
    rows: list[dict[str, Any]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        status = _read_json(child / "status.json")
        if not status:
            continue
        spec = _read_json(child / "spec.json") or {}
        status.setdefault("title", spec.get("title") or status.get("id"))
        status.setdefault("created_at", spec.get("created_at") or 0.0)
        if spec.get("source_kind"):
            status.setdefault("source_kind", spec.get("source_kind"))
        if spec.get("source_fingerprint"):
            status.setdefault("source_fingerprint", spec.get("source_fingerprint"))
        rows.append(status)
    rows.sort(key=lambda r: float(r.get("created_at") or 0.0), reverse=True)
    return rows[:limit]


_IN_FLIGHT_STATUSES = frozenset(
    {"queued", "running", "failed", "cancelled", "paused", "pausing"}
)


def list_in_flight_jobs(*, limit: int = 20) -> list[dict[str, Any]]:
    """Newest-first jobs that still belong in the compact queue (not succeeded)."""
    return [job for job in list_jobs(limit=max(limit * 2, 20)) if job.get("status") in _IN_FLIGHT_STATUSES][:limit]


def queued_job_ids() -> list[str]:
    """Oldest-first queued job ids (public wrapper)."""
    return _queued_job_ids()


def queued_wait_caption(job_id: str, queued_ids: list[str]) -> str:
    """Waiting line with queue position; never a fake percent."""
    from ui.isolate_state import queued_wait_caption as _caption

    return _caption(job_id, queued_ids)


def merge_library_runs(
    recent: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Finished runs for the mixer switcher, newest first, one row per run_dir."""
    by_dir: dict[str, dict[str, Any]] = {}
    for job in jobs:
        if job.get("status") != "succeeded":
            continue
        run_dir = str(job.get("run_dir") or "")
        if not run_dir:
            continue
        by_dir[run_dir] = {**job, "run_dir": run_dir}
    for run in recent:
        run_dir = str(run.get("run_dir") or "")
        if not run_dir:
            continue
        existing = by_dir.get(run_dir, {})
        by_dir[run_dir] = {**existing, **run, "run_dir": run_dir}
    rows = list(by_dir.values())
    rows.sort(key=lambda r: float(r.get("created_at") or 0.0), reverse=True)
    return rows


def active_job_id() -> str | None:
    """Job id the worker is starting, running, or stopping (process still alive)."""
    with _QUEUE_LOCK:
        return _ACTIVE_JOB_ID


def worker_busy() -> bool:
    """True while a child process is still running or being torn down."""
    with _QUEUE_LOCK:
        proc = _ACTIVE_PROCESS
        if proc is not None and proc.is_alive():
            return True
        return _ACTIVE_JOB_ID is not None


def _use_inline_worker() -> bool:
    return os.environ.get("ISOLATE_JOBS_INLINE", "").strip() == "1"


def _queued_job_ids() -> list[str]:
    """Oldest-first queued jobs."""
    rows = []
    for child in jobs_root().iterdir():
        if not child.is_dir():
            continue
        status = _read_json(child / "status.json")
        if not status or status.get("status") != "queued":
            continue
        spec = _read_json(child / "spec.json") or {}
        rows.append((float(spec.get("created_at") or 0.0), child.name))
    rows.sort(key=lambda t: t[0])
    return [job_id for _, job_id in rows]


def _job_process_entry(job_id: str) -> None:
    _run_one_job(job_id)


def _run_one_job(job_id: str) -> None:
    from audio_to_tab.isolate import IsolateConfig, JobAborted, separate_stems
    from audio_to_tab.hardware import (
        get_desktop_probe,
        recommended_cpu_threads,
        resolve_safe_device,
    )
    from ui.common import write_run_metadata
    from ui.isolate_state import (
        estimated_stage_seconds,
        estimate_job_seconds,
        expects_guitar_stem,
        intra_stage_fraction,
        isolation_stages_for_job,
        resolve_active_stage,
        stage_progress_percent,
    )
    from ui.media import cleanup_mix_artifacts

    spec = read_spec(job_id)
    if spec is None:
        write_status(job_id, status="failed", stage="error", message="Missing job spec", error="Missing job spec")
        return

    current = read_status(job_id)
    if current and current.get("status") in ("cancelled", "pausing"):
        return

    _clear_abort_flag(job_id)
    completed_stages = set(current.get("completed_stages") or []) if current else set()

    guitar_job = expects_guitar_stem(
        model=spec.model,
        two_stems=spec.two_stems,
        custom_stems=spec.custom_stems,
    )
    stages = isolation_stages_for_job(
        expects_guitar=guitar_job, guitar_refine=spec.guitar_refine
    )
    clip_sec = spec.audio_duration_sec
    if clip_sec is None:
        clip_sec = spec.max_duration_sec
    # Never run a job on an accelerator this host cannot use (CUDA stays fail-
    # closed; an MPS request on an ineligible Mac downgrades to CPU).
    probe = get_desktop_probe()
    try:
        spec.device = resolve_safe_device(spec.device, probe)
    except RuntimeError as exc:
        write_status(
            job_id,
            status="failed",
            stage="error",
            message=str(exc),
            error=str(exc),
            finished_at=time.time(),
        )
        return
    job_estimate, estimate_conf = estimate_job_seconds(
        audio_duration_sec=clip_sec,
        quality=spec.quality,
        device=spec.device,
        stages=stages,
        last_run=spec.prior_timing,
        model=spec.model,
        expects_guitar=guitar_job,
        two_pass=spec.two_pass,
        guitar_refine=spec.guitar_refine,
        cpu_threads=recommended_cpu_threads(),
    )
    started = time.time()
    eta_fields = {
        "audio_duration_sec": clip_sec,
        "job_estimate_sec": job_estimate,
        "estimate_confidence": estimate_conf,
        "stages": list(stages),
        "quality": spec.quality,
        "device": spec.device,
        "model": spec.model,
    }
    write_status(
        job_id,
        status="running",
        stage="ingest",
        message="Preparing audio…",
        progress=0.0,
        started_at=started,
        title=spec.title,
        stage_started_at=started,
        **eta_fields,
    )

    config = IsolateConfig(
        model=spec.model,
        quality=spec.quality,
        device=spec.device,
        start_sec=spec.start_sec,
        max_duration_sec=spec.max_duration_sec,
        two_stems=spec.two_stems,
        guitar_checkpoint=spec.guitar_checkpoint,
        two_pass=spec.two_pass,
        guitar_refine=spec.guitar_refine,
        emit_stems=tuple(spec.emit_stems) if spec.emit_stems else None,
        fold_other_into_guitar=spec.fold_other_into_guitar,
        fold_other_mode=spec.fold_other_mode,
        # Default isolate path: never emit lead/rhythm.
        lead_rhythm=False,
        lead_rhythm_mode="confident",
        low_end_restore_db=spec.low_end_restore_db,
        sub_bass_debleed=spec.sub_bass_debleed,
    )

    progress_state: dict[str, Any] = {"stage": "ingest", "stage_started_wall": started}

    def on_progress(stage: str, message: str) -> None:
        now = time.time()
        if stage != progress_state["stage"]:
            progress_state["stage_started_wall"] = now
        progress_state["stage"] = stage
        active = resolve_active_stage(stage, stages)
        elapsed_in = now - float(progress_state["stage_started_wall"])
        stage_est = estimated_stage_seconds(active, stages, job_estimate)
        intra, _est = intra_stage_fraction(elapsed_in, stage_est)
        pct = stage_progress_percent(active, stages=stages, intra=intra)
        write_status(
            job_id,
            status="running",
            stage=active,
            message=message,
            progress=pct,
            title=spec.title,
            **eta_fields,
            stage_started_at=progress_state["stage_started_wall"],
        )

    def should_abort() -> bool:
        return _abort_flag_path(job_id).is_file()

    def on_stage_complete(stage: str) -> None:
        latest = read_status(job_id) or {}
        stages_done = list(latest.get("completed_stages") or [])
        if stage not in stages_done:
            stages_done.append(stage)
        write_status(job_id, completed_stages=stages_done)

    # Cap each long-running Demucs subprocess so a wedged child cannot block the
    # worker forever; 2.5× the (already generous) job estimate + 300s slack keeps
    # legit slow CPU runs safe while still catching true hangs. The abort path
    # (pause/stop) also terminates the child mid-run via the Popen handle.
    subprocess_timeout_sec = (job_estimate * 2.5 + 300.0) if job_estimate and job_estimate > 0 else None

    try:
        artifacts = separate_stems(
            audio_path=Path(spec.audio_path),
            output_dir=Path(spec.output_dir),
            config=config,
            on_progress=on_progress,
            should_abort=should_abort,
            checkpoint_dir=_checkpoint_dir(job_id),
            completed_stages=completed_stages,
            on_stage_complete=on_stage_complete,
            subprocess_timeout_sec=subprocess_timeout_sec,
        )
        cleanup_mix_artifacts(Path(spec.output_dir))
        artifact_map = {k: str(v) for k, v in artifacts.items()}
        write_run_metadata(
            Path(spec.output_dir),
            page="isolate",
            title=spec.title,
            artifacts=artifacts,
            owner=spec.owner,
            source_kind=spec.source_kind,
            source_fingerprint=spec.source_fingerprint,
        )
        latest = read_status(job_id)
        if latest and latest.get("status") in ("cancelled", "pausing"):
            return
        write_status(
            job_id,
            status="succeeded",
            stage="done",
            message="Complete",
            progress=1.0,
            artifacts=artifact_map,
            finished_at=time.time(),
            title=spec.title,
            run_dir=spec.output_dir,
            source_fingerprint=spec.source_fingerprint,
            source_kind=spec.source_kind,
            region_label=spec.region_label,
            source_audio_path=spec.audio_path,
            custom_stems=spec.custom_stems,
            clip_length=spec.max_duration_sec,
            **eta_fields,
        )
    except JobAborted:
        return
    except Exception as exc:
        latest = read_status(job_id)
        if latest and latest.get("status") in ("cancelled", "pausing"):
            return
        write_status(
            job_id,
            status="failed",
            stage="error",
            message="Separation failed",
            error=str(exc),
            finished_at=time.time(),
            title=spec.title,
            traceback=traceback.format_exc()[-2000:],
        )


def _execute_job(job_id: str) -> None:
    global _ACTIVE_JOB_ID, _ACTIVE_PROCESS
    if _use_inline_worker():
        _run_one_job(job_id)
        _finalize_job_after_process(job_id)
        return
    proc = multiprocessing.Process(
        target=_job_process_entry,
        args=(job_id,),
        name=f"isolate-{job_id[:8]}",
    )
    proc.start()
    with _QUEUE_LOCK:
        _ACTIVE_PROCESS = proc
        _ACTIVE_JOB_ID = job_id
    proc.join()
    with _QUEUE_LOCK:
        if _ACTIVE_PROCESS is proc:
            _ACTIVE_PROCESS = None
    _finalize_job_after_process(job_id)


def _worker_loop() -> None:
    global _ACTIVE_JOB_ID, _ACTIVE_PROCESS
    while True:
        try:
            with _QUEUE_LOCK:
                queued = _queued_job_ids()
                job_id = queued[0] if queued else None
                if job_id is None:
                    _ACTIVE_JOB_ID = None
            if job_id is None:
                time.sleep(0.4)
                continue
            current = read_status(job_id)
            if current and current.get("status") == "cancelled":
                _finalize_job_after_process(job_id)
                continue
            try:
                with _QUEUE_LOCK:
                    _ACTIVE_JOB_ID = job_id
                _execute_job(job_id)
            finally:
                with _QUEUE_LOCK:
                    if _ACTIVE_JOB_ID == job_id:
                        _ACTIVE_JOB_ID = None
                    if _ACTIVE_PROCESS is not None and not _ACTIVE_PROCESS.is_alive():
                        _ACTIVE_PROCESS = None
        except Exception:
            time.sleep(1.0)


def ensure_worker_started() -> None:
    """Start the serial worker, or restart it if the thread died."""
    if os.environ.get("ISOLATE_JOBS_WORKER", "1").strip() == "0":
        return
    global _WORKER_STARTED, _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            return
        thread = threading.Thread(target=_worker_loop, name="isolate-job-worker", daemon=True)
        thread.start()
        _WORKER_THREAD = thread
        _WORKER_STARTED = True


_DIAGNOSTIC_KEYS = frozenset(
    {"guitar_split_diagnostics", "stem_presence_diagnostics", "bass_bleed_diagnostics"}
)
_MIXER_RESET_KEYS = (
    "isolate_volumes_db",
    "isolate_master_volume_db",
    "isolate_mixer_state",
    "isolate_mix_ready",
    "isolate_mix_fp",
)


def _existing_wav_artifacts(artifacts: dict[str, Any]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for name, path in (artifacts or {}).items():
        if name in _DIAGNOSTIC_KEYS:
            continue
        wav = Path(str(path))
        if wav.suffix.lower() != ".wav" or not wav.exists():
            continue
        out[str(name)] = wav
    return out


def _results_fingerprint(stem_paths: dict[str, Path]) -> str:
    payload = "|".join(f"{k}:{v}" for k, v in sorted((n, str(p)) for n, p in stem_paths.items()))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _presence_from_artifacts(artifacts: dict[str, Any]) -> dict[str, Any]:
    path = artifacts.get("stem_presence_diagnostics")
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def apply_succeeded_job_to_session(
    session: Any,
    status: dict[str, Any],
    *,
    viewing_mode: str | None = None,
) -> bool:
    """Copy a finished job's artifacts into Streamlit session_state keys.

    Returns True when artifacts were applied. Missing wavs return False and
    leave session unchanged.
    """
    if status.get("status") != "succeeded":
        return False
    artifacts = status.get("artifacts") or {}
    wav_paths = _existing_wav_artifacts(artifacts)
    if not wav_paths:
        return False
    produced = list(wav_paths.keys())
    custom = list(status.get("custom_stems") or [])
    presence = _presence_from_artifacts(artifacts)
    from ui.isolate_state import custom_selected_stems, infer_source_kind

    if custom:
        selected = custom_selected_stems(produced, custom)
    else:
        selected = {
            name: bool(presence.get(name, {}).get("present", True)) for name in produced
        }

    session["isolate_artifacts"] = dict(artifacts)
    session["isolate_base_name"] = status.get("title") or "tracks"
    run_dir = status.get("run_dir")
    if run_dir:
        session["isolate_run_dir"] = run_dir
    if status.get("source_audio_path"):
        session["isolate_source_audio_path"] = status["source_audio_path"]
    if status.get("source_fingerprint"):
        session["isolate_results_source_fp"] = status["source_fingerprint"]
    session["isolate_source_kind"] = infer_source_kind(
        source_kind=status.get("source_kind"),
        source_fingerprint=status.get("source_fingerprint"),
    )
    if status.get("region_label"):
        session["isolate_region_label"] = status["region_label"]
    else:
        session.pop("isolate_region_label", None)
    clip_length = status.get("clip_length")
    if clip_length is None:
        clip_length = status.get("max_duration_sec")
    if clip_length is not None:
        session["isolate_clip_length"] = float(clip_length)
    else:
        session.pop("isolate_clip_length", None)
    session["isolate_results_fp"] = _results_fingerprint(wav_paths)
    session["isolate_selected_stems"] = selected
    session["isolate_consumed_job_id"] = status.get("id")
    mode = viewing_mode if viewing_mode is not None else str(status.get("id") or "latest")
    session["isolate_viewing_job_id"] = mode
    if run_dir:
        session["isolate_viewing_run_dir"] = str(run_dir)
    for key in _MIXER_RESET_KEYS:
        session.pop(key, None)
    return True
