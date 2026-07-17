"""API contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobKind(str, Enum):
    tab = "tab"
    isolate = "isolate"


class JobCreateRequest(BaseModel):
    upload_id: str | None = None
    youtube_url: str | None = None
    title: str = "Guitar Tab"
    separate_stems: bool = True
    max_duration_sec: float = 90.0
    mix_aware_filtering: bool = True
    tempo_bpm_override: float | None = None
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3


class IsolateJobCreateRequest(BaseModel):
    upload_id: str
    model: str = "htdemucs_6s"
    quality: str = "balanced"
    device: str = "cpu"
    max_duration_sec: float = 90.0
    two_stems: str | None = None
    dual_guitar: bool = False


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    kind: JobKind = JobKind.tab
    stage: str = ""
    message: str = ""
    error: str | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)


class UploadResponse(BaseModel):
    upload_id: str
    filename: str


class JobEvent(BaseModel):
    job_id: str
    stage: str
    message: str
    status: JobStatus
    artifacts: dict[str, str] = Field(default_factory=dict)
