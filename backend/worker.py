"""arq worker entrypoint for durable jobs."""

from __future__ import annotations

from pathlib import Path

from arq.connections import RedisSettings

from backend.config import settings
from backend.db import init_db
from backend.jobs.manager import JobManager
from backend.jobs.runner import run_isolate_job_async, run_job_async


async def startup(ctx) -> None:
    init_db()
    ctx["job_manager"] = JobManager(Path(settings.data_dir))


async def process_tab_job(ctx, job_id: str) -> None:
    await run_job_async(ctx["job_manager"], job_id)


async def process_isolate_job(ctx, job_id: str) -> None:
    await run_isolate_job_async(ctx["job_manager"], job_id)


class WorkerSettings:
    functions = [process_tab_job, process_isolate_job]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 1  # Demucs is heavy; one job at a time per worker
    job_timeout = settings.job_timeout_extreme_sec
