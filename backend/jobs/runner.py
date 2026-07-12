"""Pipeline job runner."""

from __future__ import annotations

import asyncio
from pathlib import Path

from backend.contracts import JobStatus
from backend.jobs.manager import JobManager
from audio_to_tab.pipeline import PipelineConfig, run_pipeline


async def run_job_async(job_manager: JobManager, job_id: str) -> None:
    job = job_manager.get(job_id)
    if not job:
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
