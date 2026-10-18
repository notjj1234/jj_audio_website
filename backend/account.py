"""Account / personal-data deletion (compliance C20)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.models import Job, JobArtifact, Upload, User
from backend.storage import Storage

logger = logging.getLogger(__name__)


def delete_user_account(db: Session, user: User, storage: Storage) -> dict[str, int]:
    """Delete a user row and best-effort purge uploads/job artifacts from storage.

    Returns counts for operators/UI. Storage delete failures are logged and skipped
    so the DB row can still be removed (demo environments).
    """
    deleted_artifacts = 0
    deleted_uploads = 0

    jobs = db.query(Job).filter(Job.user_id == user.id).all()
    for job in jobs:
        arts = db.query(JobArtifact).filter(JobArtifact.job_id == job.id).all()
        for art in arts:
            try:
                storage.delete(art.storage_key)
                deleted_artifacts += 1
            except Exception as exc:
                logger.warning("artifact delete failed %s: %s", art.storage_key, exc)
        db.delete(job)

    uploads = db.query(Upload).filter(Upload.user_id == user.id).all()
    for upload in uploads:
        try:
            storage.delete(upload.storage_key)
            deleted_uploads += 1
        except Exception as exc:
            logger.warning("upload delete failed %s: %s", upload.storage_key, exc)
        db.delete(upload)

    db.delete(user)
    db.commit()
    return {
        "deleted_jobs": len(jobs),
        "deleted_artifacts": deleted_artifacts,
        "deleted_uploads": deleted_uploads,
    }
