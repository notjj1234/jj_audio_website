"""FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.config import settings
from backend.contracts import JobCreateRequest, JobResponse, JobStatus, UploadResponse
from backend.jobs.manager import JobManager
from backend.jobs.runner import run_job_async

app = FastAPI(title="Audio to Tab PDF", version="0.1.0")

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
    return JobResponse(id=job.id, status=JobStatus.pending)


@app.get("/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobResponse(
        id=job.id,
        status=job.status,
        stage=job.stage,
        message=job.message,
        error=job.error,
        artifacts=job.artifacts,
    )


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
    media = {"pdf": "application/pdf", "midi": "audio/midi", "tab": "text/plain", "guitar_stem": "audio/wav"}
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
