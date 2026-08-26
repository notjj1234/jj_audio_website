"""Durable job manager backed by Postgres/SQLite + object storage."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from backend.config import settings
from backend.contracts import JobEvent, JobKind, JobStatus
from backend import db as db_module
from backend.events import event_bus
from backend.models import Job, JobArtifact, JobKindDB, JobStatusDB, Upload
from backend.storage import LocalStorage, get_storage


@dataclass
class JobRecord:
    """In-memory view used by runners (loaded from DB)."""

    id: str
    user_id: str
    kind: JobKind = JobKind.tab
    status: JobStatus = JobStatus.pending
    stage: str = "pending"
    message: str = ""
    error: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    upload_path: str | None = None
    youtube_url: str | None = None
    title: str = "Guitar Tab"
    separate_stems: bool = True
    max_duration_sec: float | None = 90.0
    mix_aware_filtering: bool = True
    tempo_bpm_override: float | None = None
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    isolate_model: str = "htdemucs_6s"
    isolate_quality: str = "fast"
    isolate_device: str = "cpu"
    demucs_quality: str = "balanced"
    demucs_device: str = "cpu"
    isolate_two_stems: str | None = None
    isolate_lead_rhythm: bool = False
    isolate_lead_rhythm_mode: str = "confident"
    isolate_guitar_checkpoint: str | None = None
    isolate_dual_guitar: bool = False
    isolate_start_sec: float = 0.0
    cancel_requested: bool = False
    work_dir: str | None = None


def _status_from_db(s: JobStatusDB) -> JobStatus:
    return JobStatus(s.value)


def _kind_from_db(k: JobKindDB) -> JobKind:
    return JobKind(k.value)


class JobManager:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.uploads_dir = data_dir / "uploads"
        self.jobs_dir = data_dir / "jobs"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._local_work: dict[str, Path] = {}

    def save_upload_stream(self, filename: str, chunks, user_id: str) -> tuple[str, str]:
        """Save upload chunks to storage. Returns (upload_id, storage_key)."""
        upload_id = str(uuid.uuid4())
        key = f"uploads/{user_id}/{upload_id}/{filename}"
        storage = get_storage()
        if isinstance(storage, LocalStorage):
            dest = storage.local_path(key)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as f:
                for chunk in chunks:
                    f.write(chunk)
        else:
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
                for chunk in chunks:
                    tmp.write(chunk)
                tmp_path = Path(tmp.name)
            try:
                storage.put_file(key, tmp_path)
            finally:
                tmp_path.unlink(missing_ok=True)

        db = db_module.SessionLocal()
        try:
            db.add(
                Upload(
                    id=upload_id,
                    user_id=user_id,
                    storage_key=key,
                    filename=filename,
                )
            )
            db.commit()
        finally:
            db.close()
        return upload_id, key

    def save_upload(self, filename: str, content: bytes, user_id: str) -> tuple[str, Path]:
        upload_id, key = self.save_upload_stream(filename, [content], user_id)
        storage = get_storage()
        if isinstance(storage, LocalStorage):
            return upload_id, storage.local_path(key)
        path = storage.open_temp(key, suffix=Path(filename).suffix)
        return upload_id, path

    def resolve_upload_key(self, upload_id: str, user_id: str) -> str | None:
        db = db_module.SessionLocal()
        try:
            row = db.query(Upload).filter(Upload.id == upload_id, Upload.user_id == user_id).first()
            if not row:
                return None
            return row.storage_key
        finally:
            db.close()

    def create_job(
        self,
        *,
        user_id: str,
        upload_id: str | None = None,
        upload_key: str | None = None,
        youtube_url: str | None = None,
        title: str = "Guitar Tab",
        separate_stems: bool = True,
        max_duration_sec: float = 90.0,
        mix_aware_filtering: bool = True,
        tempo_bpm_override: float | None = None,
        onset_threshold: float = 0.5,
        frame_threshold: float = 0.3,
        demucs_quality: str = "balanced",
        demucs_device: str = "cpu",
    ) -> JobRecord:
        if upload_id and not upload_key:
            upload_key = self.resolve_upload_key(upload_id, user_id)
            if not upload_key:
                raise FileNotFoundError(f"Upload not found: {upload_id}")
        job_id = str(uuid.uuid4())
        config = {
            "upload_id": upload_id,
            "upload_key": upload_key,
            "youtube_url": youtube_url,
            "title": title,
            "separate_stems": separate_stems,
            "max_duration_sec": max_duration_sec,
            "mix_aware_filtering": mix_aware_filtering,
            "tempo_bpm_override": tempo_bpm_override,
            "onset_threshold": onset_threshold,
            "frame_threshold": frame_threshold,
            "demucs_quality": demucs_quality,
            "demucs_device": demucs_device,
        }
        db = db_module.SessionLocal()
        try:
            row = Job(
                id=job_id,
                user_id=user_id,
                kind=JobKindDB.tab,
                status=JobStatusDB.pending,
                stage="pending",
                message="Queued",
                config=config,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

        work = self.jobs_dir / job_id
        work.mkdir(parents=True, exist_ok=True)
        self._local_work[job_id] = work
        return self.get(job_id)  # type: ignore[return-value]

    def create_isolate_job(
        self,
        *,
        user_id: str,
        upload_id: str,
        upload_key: str | None = None,
        model: str = "htdemucs_6s",
        quality: str = "fast",
        device: str = "cpu",
        start_sec: float = 0.0,
        max_duration_sec: float | None = None,
        two_stems: str | None = None,
        lead_rhythm: bool = False,
        lead_rhythm_mode: str | None = None,
        guitar_checkpoint: str | None = None,
        dual_guitar: bool = False,
    ) -> JobRecord:
        if not upload_key:
            upload_key = self.resolve_upload_key(upload_id, user_id)
        if not upload_key:
            raise FileNotFoundError(f"Upload not found: {upload_id}")

        job_id = str(uuid.uuid4())
        effective_lr = bool(lead_rhythm or dual_guitar)
        mode = lead_rhythm_mode
        if mode is None:
            mode = "best_effort" if effective_lr else "confident"
        config = {
            "upload_id": upload_id,
            "upload_key": upload_key,
            "model": model,
            "quality": quality,
            "device": device,
            "start_sec": start_sec,
            "max_duration_sec": max_duration_sec,
            "two_stems": two_stems,
            "lead_rhythm": effective_lr,
            "lead_rhythm_mode": mode,
            "guitar_checkpoint": guitar_checkpoint,
            "dual_guitar": dual_guitar,
            "timeout_sec": settings.job_timeout_for_quality(quality),
        }
        db = db_module.SessionLocal()
        try:
            row = Job(
                id=job_id,
                user_id=user_id,
                kind=JobKindDB.isolate,
                status=JobStatusDB.pending,
                stage="pending",
                message="Queued",
                config=config,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

        work = self.jobs_dir / job_id
        work.mkdir(parents=True, exist_ok=True)
        self._local_work[job_id] = work
        return self.get(job_id)  # type: ignore[return-value]

    def _row_to_record(self, row: Job) -> JobRecord:
        cfg = row.config or {}
        arts = {a.kind: a.storage_key for a in row.artifacts}
        upload_key = cfg.get("upload_key")
        upload_path = None
        if upload_key:
            storage = get_storage()
            if isinstance(storage, LocalStorage):
                p = storage.local_path(upload_key)
                if p.exists():
                    upload_path = str(p)

        return JobRecord(
            id=row.id,
            user_id=row.user_id,
            kind=_kind_from_db(row.kind),
            status=_status_from_db(row.status),
            stage=row.stage,
            message=row.message,
            error=row.error,
            artifacts=arts,
            upload_path=upload_path,
            youtube_url=cfg.get("youtube_url"),
            title=cfg.get("title", "Guitar Tab"),
            separate_stems=bool(cfg.get("separate_stems", True)),
            max_duration_sec=cfg.get("max_duration_sec", 90.0),
            mix_aware_filtering=bool(cfg.get("mix_aware_filtering", True)),
            tempo_bpm_override=cfg.get("tempo_bpm_override"),
            onset_threshold=float(cfg.get("onset_threshold", 0.5)),
            frame_threshold=float(cfg.get("frame_threshold", 0.3)),
            isolate_model=cfg.get("model", "htdemucs_6s"),
            isolate_quality=cfg.get("quality", "fast"),
            isolate_device=cfg.get("device", "cpu"),
            demucs_quality=cfg.get("demucs_quality", "balanced"),
            demucs_device=cfg.get("demucs_device", "cpu"),
            isolate_two_stems=cfg.get("two_stems"),
            isolate_lead_rhythm=bool(cfg.get("lead_rhythm", False)),
            isolate_lead_rhythm_mode=str(cfg.get("lead_rhythm_mode", "confident")),
            isolate_guitar_checkpoint=cfg.get("guitar_checkpoint"),
            isolate_dual_guitar=bool(cfg.get("dual_guitar", False)),
            isolate_start_sec=float(cfg.get("start_sec", 0.0)),
            cancel_requested=bool(row.cancel_requested),
            work_dir=str(self.jobs_dir / row.id),
        )

    def get(self, job_id: str) -> JobRecord | None:
        db = db_module.SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job_id).first()
            if not row:
                return None
            return self._row_to_record(row)
        finally:
            db.close()

    def get_owned(self, job_id: str, user_id: str) -> JobRecord | None:
        db = db_module.SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
            if not row:
                return None
            return self._row_to_record(row)
        finally:
            db.close()

    def list_owned(
        self,
        user_id: str,
        *,
        kind: JobKind | None = None,
        limit: int = 20,
    ) -> list[JobRecord]:
        """Newest-first jobs for a user (serial queue UI)."""
        db = db_module.SessionLocal()
        try:
            q = db.query(Job).filter(Job.user_id == user_id)
            if kind is not None:
                q = q.filter(Job.kind == JobKindDB(kind.value))
            rows = q.order_by(Job.created_at.desc()).limit(limit).all()
            return [self._row_to_record(r) for r in rows]
        finally:
            db.close()

    def job_output_dir(self, job_id: str) -> Path:
        path = self.jobs_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def request_cancel(self, job_id: str) -> bool:
        db = db_module.SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job_id).first()
            if not row:
                return False
            if row.status in (JobStatusDB.succeeded, JobStatusDB.failed, JobStatusDB.cancelled):
                return False
            row.cancel_requested = True
            if row.status == JobStatusDB.pending:
                row.status = JobStatusDB.cancelled
                row.stage = "cancelled"
                row.message = "Cancelled"
            db.commit()
            return True
        finally:
            db.close()

    def is_cancel_requested(self, job_id: str) -> bool:
        db = db_module.SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job_id).first()
            return bool(row and row.cancel_requested)
        finally:
            db.close()

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        return await event_bus.subscribe(job_id)

    async def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        await event_bus.unsubscribe(job_id, q)

    async def emit(
        self, job_id: str, stage: str, message: str, status: JobStatus | None = None
    ) -> None:
        db = db_module.SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job_id).first()
            if not row:
                return
            row.stage = stage
            row.message = message
            if status:
                row.status = JobStatusDB(status.value)
            arts = {a.kind: a.storage_key for a in row.artifacts}
            kind = _kind_from_db(row.kind)
            current = _status_from_db(row.status)
            db.commit()
        finally:
            db.close()

        event = JobEvent(
            job_id=job_id,
            stage=stage,
            message=message,
            status=status if status is not None else current,
            artifacts=arts,
            kind=kind,
        )
        await event_bus.publish(event)

    def set_artifacts(self, job_id: str, artifacts: dict[str, str]) -> None:
        """artifacts maps kind -> local filesystem path; uploads to storage."""
        storage = get_storage()
        db = db_module.SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job_id).first()
            if not row:
                return
            db.query(JobArtifact).filter(JobArtifact.job_id == job_id).delete()
            stored: dict[str, str] = {}
            for kind, path_str in artifacts.items():
                path = Path(path_str)
                key = f"jobs/{job_id}/{path.name}"
                if path.exists():
                    storage.put_file(key, path)
                    db.add(
                        JobArtifact(
                            job_id=job_id,
                            kind=kind,
                            storage_key=key,
                            filename=path.name,
                        )
                    )
                    stored[kind] = key
            db.commit()
        finally:
            db.close()

    def set_failed(self, job_id: str, error: str) -> None:
        db = db_module.SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job_id).first()
            if not row:
                return
            row.status = JobStatusDB.failed
            row.error = error
            row.stage = "error"
            row.message = error
            db.commit()
        finally:
            db.close()

    def set_succeeded(self, job_id: str) -> None:
        db = db_module.SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job_id).first()
            if not row:
                return
            row.status = JobStatusDB.succeeded
            row.stage = "done"
            row.message = "Complete"
            db.commit()
        finally:
            db.close()

    def set_cancelled(self, job_id: str) -> None:
        db = db_module.SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job_id).first()
            if not row:
                return
            row.status = JobStatusDB.cancelled
            row.stage = "cancelled"
            row.message = "Cancelled"
            db.commit()
        finally:
            db.close()

    def artifact_urls(self, job: JobRecord, user_id: str) -> dict[str, str]:
        from backend.auth import sign_artifact_token

        urls: dict[str, str] = {}
        for kind in job.artifacts:
            token = sign_artifact_token(job.id, kind, user_id)
            urls[kind] = f"/v1/artifacts/{job.id}/{kind}/signed?token={token}&uid={user_id}"
        return urls

    def materialize_upload(self, job: JobRecord) -> Path | None:
        """Ensure job.upload_path points to a local file."""
        if job.upload_path and Path(job.upload_path).exists():
            return Path(job.upload_path)
        db = db_module.SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job.id).first()
            if not row:
                return None
            key = (row.config or {}).get("upload_key")
        finally:
            db.close()
        if not key:
            return None
        storage = get_storage()
        if isinstance(storage, LocalStorage):
            p = storage.local_path(key)
            if p.exists():
                return p
        dest = self.job_output_dir(job.id) / Path(key).name
        return storage.get_file(key, dest)
