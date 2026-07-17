"""FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.config import settings
from backend.contracts import (
    IsolateJobCreateRequest,
    JobCreateRequest,
    JobResponse,
    JobStatus,
    UploadResponse,
)
from backend.jobs.manager import JobManager
from backend.jobs.runner import run_isolate_job_async, run_job_async
from audio_to_tab.isolate import SUPPORTED_MODELS

app = FastAPI(title="Audio Tools API", version="0.2.0")

origins = ["*"] if settings.cors_origins == "*" else settings.cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_dir = Path(settings.data_dir)
job_manager = JobManager(data_dir)


def _job_response(job) -> JobResponse:
    return JobResponse(
        id=job.id,
        status=job.status,
        kind=job.kind,
        stage=job.stage,
        message=job.message,
        error=job.error,
        artifacts=job.artifacts,
    )


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/uploads/audio", response_model=UploadResponse)
async def upload_audio(file: UploadFile = File(...)) -> UploadResponse:
    content = await file.read()
    upload_id, _ = job_manager.save_upload(file.filename or "audio.wav", content)
    return UploadResponse(upload_id=upload_id, filename=file.filename or "audio.wav")


@app.post("/v1/jobs", response_model=JobResponse)
async def create_job(body: JobCreateRequest, background_tasks: BackgroundTasks) -> JobResponse:
    if not body.upload_id and not body.youtube_url:
        raise HTTPException(400, "Provide upload_id or youtube_url")

    job = job_manager.create_job(
        upload_id=body.upload_id,
        youtube_url=body.youtube_url,
        title=body.title,
        separate_stems=body.separate_stems,
        max_duration_sec=body.max_duration_sec,
        mix_aware_filtering=body.mix_aware_filtering,
        tempo_bpm_override=body.tempo_bpm_override,
        onset_threshold=body.onset_threshold,
        frame_threshold=body.frame_threshold,
    )
    background_tasks.add_task(run_job_async, job_manager, job.id)
    return _job_response(job)


@app.post("/v1/isolate/jobs", response_model=JobResponse)
async def create_isolate_job(
    body: IsolateJobCreateRequest, background_tasks: BackgroundTasks
) -> JobResponse:
    if body.model not in SUPPORTED_MODELS:
        raise HTTPException(400, f"Unsupported model. Choose from: {', '.join(SUPPORTED_MODELS)}")
    if body.quality not in ("fast", "balanced", "high", "extreme"):
        raise HTTPException(400, "quality must be fast|balanced|high|extreme")

    try:
        job = job_manager.create_isolate_job(
            upload_id=body.upload_id,
            model=body.model,
            quality=body.quality,
            device=body.device,
            max_duration_sec=body.max_duration_sec,
            two_stems=body.two_stems,
            lead_rhythm=body.lead_rhythm,
            dual_guitar=body.dual_guitar,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None

    background_tasks.add_task(run_isolate_job_async, job_manager, job.id)
    return _job_response(job)


@app.get("/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_response(job)


@app.get("/v1/artifacts/{job_id}/{kind}")
def get_artifact(job_id: str, kind: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    path_str = job.artifacts.get(kind)
    if not path_str:
        raise HTTPException(404, f"Artifact '{kind}' not found")
    path = Path(path_str)
    if not path.exists():
        raise HTTPException(404, "Artifact file missing")
    media = {
        "pdf": "application/pdf",
        "midi": "audio/midi",
        "tab": "text/plain",
        "guitar_stem": "audio/wav",
        "zip": "application/zip",
        "vocals": "audio/wav",
        "drums": "audio/wav",
        "bass": "audio/wav",
        "other": "audio/wav",
        "guitar": "audio/wav",
        "lead_guitar": "audio/wav",
        "rhythm_guitar": "audio/wav",
        "guitar1": "audio/wav",
        "guitar2": "audio/wav",
        "piano": "audio/wav",
        "no_vocals": "audio/wav",
        "no_drums": "audio/wav",
        "no_bass": "audio/wav",
        "no_other": "audio/wav",
        "no_guitar": "audio/wav",
        "no_piano": "audio/wav",
        "guitar_split_diagnostics": "application/json",
    }
    return FileResponse(path, media_type=media.get(kind, "application/octet-stream"), filename=path.name)


@app.websocket("/v1/jobs/{job_id}/ws")
async def job_ws(websocket: WebSocket, job_id: str) -> None:
    job = job_manager.get(job_id)
    if not job:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    q = await job_manager.subscribe(job_id)
    try:
        await websocket.send_json(
            {
                "job_id": job_id,
                "stage": job.stage,
                "message": job.message,
                "status": job.status.value,
                "kind": job.kind.value,
                "artifacts": job.artifacts,
            }
        )
        while True:
            event = await q.get()
            await websocket.send_json(event.model_dump())
            if event.status in (JobStatus.succeeded, JobStatus.failed):
                break
    except WebSocketDisconnect:
        pass
    finally:
        job_manager.unsubscribe(job_id, q)


def main() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
