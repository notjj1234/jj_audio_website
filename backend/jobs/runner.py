"""Pipeline and isolation job runners."""

from __future__ import annotations

import asyncio
import logging
import zipfile
from pathlib import Path

from backend.config import settings
from backend.contracts import JobKind, JobStatus
from backend.jobs import single_flight
from backend.jobs.manager import JobManager
from audio_to_tab.isolate import IsolateConfig, separate_stems
from audio_to_tab.pipeline import PipelineConfig, run_pipeline

logger = logging.getLogger(__name__)


def _public_job_error(exc: BaseException) -> str:
    if settings.env != "production":
        return str(exc)
    return "Job failed"


async def run_job_async(job_manager: JobManager, job_id: str) -> None:
    try:
        await _run_job_async(job_manager, job_id)
    finally:
        if settings.single_flight_jobs:
            single_flight.release()


async def _run_job_async(job_manager: JobManager, job_id: str) -> None:
    job = job_manager.get(job_id)
    if not job:
        return

    if job.kind == JobKind.isolate:
        await _run_isolate_job_async(job_manager, job_id)
        return

    if job_manager.is_cancel_requested(job_id):
        job_manager.set_cancelled(job_id)
        await job_manager.emit(job_id, "cancelled", "Cancelled", JobStatus.cancelled)
        return

    await job_manager.emit(job_id, "pending", "Job queued", JobStatus.running)
    output_dir = job_manager.job_output_dir(job_id)
    loop = asyncio.get_running_loop()

    async def emit_progress(stage: str, message: str) -> None:
        if job_manager.is_cancel_requested(job_id):
            raise asyncio.CancelledError("cancel requested")
        await job_manager.emit(job_id, stage, message, JobStatus.running)

    def sync_progress(stage: str, message: str) -> None:
        future = asyncio.run_coroutine_threadsafe(emit_progress(stage, message), loop)
        future.result(timeout=60)

    upload_path = job_manager.materialize_upload(job)
    timeout = settings.job_timeout_for_quality(job.demucs_quality)

    try:
        config = PipelineConfig(
            separate_stems=job.separate_stems,
            max_duration_sec=job.max_duration_sec,
            title=job.title,
            mix_aware_filtering=job.mix_aware_filtering,
            tempo_bpm_override=job.tempo_bpm_override,
            onset_threshold=job.onset_threshold,
            frame_threshold=job.frame_threshold,
            demucs_quality=job.demucs_quality,
            demucs_device=job.demucs_device,
        )

        artifacts = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: run_pipeline(
                    audio_path=upload_path,
                    youtube_url=job.youtube_url,
                    output_dir=output_dir,
                    config=config,
                    on_progress=sync_progress,
                ),
            ),
            timeout=timeout,
        )

        if job_manager.is_cancel_requested(job_id):
            job_manager.set_cancelled(job_id)
            await job_manager.emit(job_id, "cancelled", "Cancelled", JobStatus.cancelled)
            return

        artifact_map = {k: str(v) for k, v in artifacts.items()}
        job_manager.set_artifacts(job_id, artifact_map)
        job_manager.set_succeeded(job_id)
        await job_manager.emit(job_id, "done", "Complete", JobStatus.succeeded)
    except asyncio.CancelledError:
        job_manager.set_cancelled(job_id)
        await job_manager.emit(job_id, "cancelled", "Cancelled", JobStatus.cancelled)
    except asyncio.TimeoutError:
        job_manager.set_failed(job_id, "Job timed out")
        await job_manager.emit(job_id, "error", "Job timed out", JobStatus.failed)
    except Exception as exc:
        logger.exception("Tab job %s failed", job_id)
        message = _public_job_error(exc)
        job_manager.set_failed(job_id, message)
        await job_manager.emit(job_id, "error", message, JobStatus.failed)


async def run_isolate_job_async(job_manager: JobManager, job_id: str) -> None:
    """Public entry used by arq worker; honors single-flight release when enabled."""
    try:
        await _run_isolate_job_async(job_manager, job_id)
    finally:
        if settings.single_flight_jobs:
            single_flight.release()


async def _run_isolate_job_async(job_manager: JobManager, job_id: str) -> None:
    job = job_manager.get(job_id)
    if not job:
        return

    if job_manager.is_cancel_requested(job_id):
        job_manager.set_cancelled(job_id)
        await job_manager.emit(job_id, "cancelled", "Cancelled", JobStatus.cancelled)
        return

    await job_manager.emit(job_id, "pending", "Isolation job queued", JobStatus.running)
    output_dir = job_manager.job_output_dir(job_id)
    loop = asyncio.get_running_loop()
    upload_path = job_manager.materialize_upload(job)
    if not upload_path:
        job_manager.set_failed(job_id, "Upload missing")
        await job_manager.emit(job_id, "error", "Upload missing", JobStatus.failed)
        return

    async def emit_progress(stage: str, message: str) -> None:
        if job_manager.is_cancel_requested(job_id):
            raise asyncio.CancelledError("cancel requested")
        await job_manager.emit(job_id, stage, message, JobStatus.running)

    def sync_progress(stage: str, message: str) -> None:
        future = asyncio.run_coroutine_threadsafe(emit_progress(stage, message), loop)
        future.result(timeout=60)

    timeout = settings.job_timeout_for_quality(job.isolate_quality)

    try:
        config = IsolateConfig(
            model=job.isolate_model,
            quality=job.isolate_quality,
            device=job.isolate_device,
            start_sec=job.isolate_start_sec,
            max_duration_sec=job.max_duration_sec,
            two_stems=job.isolate_two_stems,
            lead_rhythm=job.isolate_lead_rhythm or job.isolate_dual_guitar,
        )

        artifacts = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: separate_stems(
                    audio_path=upload_path,
                    output_dir=output_dir,
                    config=config,
                    on_progress=sync_progress,
                ),
            ),
            timeout=timeout,
        )

        if job_manager.is_cancel_requested(job_id):
            job_manager.set_cancelled(job_id)
            await job_manager.emit(job_id, "cancelled", "Cancelled", JobStatus.cancelled)
            return

        artifact_map = {k: str(v) for k, v in artifacts.items()}

        zip_path = output_dir / "stems.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, path in artifacts.items():
                p = Path(path)
                arc = p.name if p.suffix else f"{name}.wav"
                zf.write(p, arcname=arc)
        artifact_map["zip"] = str(zip_path)

        job_manager.set_artifacts(job_id, artifact_map)
        job_manager.set_succeeded(job_id)
        await job_manager.emit(job_id, "done", "Complete", JobStatus.succeeded)
    except asyncio.CancelledError:
        job_manager.set_cancelled(job_id)
        await job_manager.emit(job_id, "cancelled", "Cancelled", JobStatus.cancelled)
    except asyncio.TimeoutError:
        job_manager.set_failed(job_id, "Job timed out")
        await job_manager.emit(job_id, "error", "Job timed out", JobStatus.failed)
    except Exception as exc:
        logger.exception("Isolate job %s failed", job_id)
        message = _public_job_error(exc)
        job_manager.set_failed(job_id, message)
        await job_manager.emit(job_id, "error", message, JobStatus.failed)
