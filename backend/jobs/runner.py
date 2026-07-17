"""Pipeline and isolation job runners."""

from __future__ import annotations

import asyncio
import zipfile
from pathlib import Path

from backend.contracts import JobKind, JobStatus
from backend.jobs.manager import JobManager
from audio_to_tab.isolate import IsolateConfig, separate_stems
from audio_to_tab.pipeline import PipelineConfig, run_pipeline


async def run_job_async(job_manager: JobManager, job_id: str) -> None:
    job = job_manager.get(job_id)
    if not job:
        return

    if job.kind == JobKind.isolate:
        await run_isolate_job_async(job_manager, job_id)
        return

    await job_manager.emit(job_id, "pending", "Job queued", JobStatus.running)
    output_dir = job_manager.job_output_dir(job_id)
    loop = asyncio.get_running_loop()

    async def emit_progress(stage: str, message: str) -> None:
        await job_manager.emit(job_id, stage, message, JobStatus.running)

    def sync_progress(stage: str, message: str) -> None:
        future = asyncio.run_coroutine_threadsafe(emit_progress(stage, message), loop)
        future.result(timeout=60)

    try:
        config = PipelineConfig(
            separate_stems=job.separate_stems,
            max_duration_sec=job.max_duration_sec,
            title=job.title,
            mix_aware_filtering=job.mix_aware_filtering,
            tempo_bpm_override=job.tempo_bpm_override,
            onset_threshold=job.onset_threshold,
            frame_threshold=job.frame_threshold,
        )

        artifacts = await loop.run_in_executor(
            None,
            lambda: run_pipeline(
                audio_path=Path(job.upload_path) if job.upload_path else None,
                youtube_url=job.youtube_url,
                output_dir=output_dir,
                config=config,
                on_progress=sync_progress,
            ),
        )

        artifact_map = {k: str(v) for k, v in artifacts.items()}
        job_manager.set_artifacts(job_id, artifact_map)
        job_manager.set_succeeded(job_id)
        await job_manager.emit(job_id, "done", "Complete", JobStatus.succeeded)
    except Exception as exc:
        job_manager.set_failed(job_id, str(exc))
        await job_manager.emit(job_id, "error", str(exc), JobStatus.failed)


async def run_isolate_job_async(job_manager: JobManager, job_id: str) -> None:
    job = job_manager.get(job_id)
    if not job or not job.upload_path:
        return

    await job_manager.emit(job_id, "pending", "Isolation job queued", JobStatus.running)
    output_dir = job_manager.job_output_dir(job_id)
    loop = asyncio.get_running_loop()

    async def emit_progress(stage: str, message: str) -> None:
        await job_manager.emit(job_id, stage, message, JobStatus.running)

    def sync_progress(stage: str, message: str) -> None:
        future = asyncio.run_coroutine_threadsafe(emit_progress(stage, message), loop)
        future.result(timeout=60)

    try:
        config = IsolateConfig(
            model=job.isolate_model,
            quality=job.isolate_quality,
            device=job.isolate_device,
            max_duration_sec=job.max_duration_sec,
            two_stems=job.isolate_two_stems,
            lead_rhythm=job.isolate_lead_rhythm or job.isolate_dual_guitar,
        )

        artifacts = await loop.run_in_executor(
            None,
            lambda: separate_stems(
                audio_path=Path(job.upload_path),
                output_dir=output_dir,
                config=config,
                on_progress=sync_progress,
            ),
        )

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
    except Exception as exc:
        job_manager.set_failed(job_id, str(exc))
        await job_manager.emit(job_id, "error", str(exc), JobStatus.failed)
