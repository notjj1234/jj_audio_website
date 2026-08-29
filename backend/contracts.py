"""API contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class JobKind(str, Enum):
    tab = "tab"
    isolate = "isolate"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _email_shape(cls, v: str) -> str:
        value = v.strip()
        if " " in value or value.count("@") != 1:
            raise ValueError("Invalid email")
        local, _, domain = value.partition("@")
        if not local or not domain:
            raise ValueError("Invalid email")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


class JobCreateRequest(BaseModel):
    upload_id: str | None = Field(default=None, max_length=36)
    youtube_url: str | None = Field(default=None, max_length=2048)
    title: str = Field(default="Guitar Tab", min_length=1, max_length=200)
    separate_stems: bool = True
    max_duration_sec: float = Field(default=90.0, ge=1, le=3600)
    mix_aware_filtering: bool = True
    tempo_bpm_override: float | None = Field(default=None, ge=20, le=400)
    onset_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    frame_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    processing_mode: str | None = Field(default=None, max_length=32)
    model: str = Field(default="htdemucs_6s", max_length=64)
    guitar_refine: bool = False
    guitar_checkpoint: str | None = Field(default=None, max_length=64)
    low_end_restore_db: float = Field(default=0.0, ge=0.0, le=12.0)
    sub_bass_debleed: bool = False


class IsolateJobCreateRequest(BaseModel):
    upload_id: str = Field(min_length=1, max_length=36)
    model: str = Field(default="htdemucs_6s", max_length=64)
    quality: str = Field(default="fast", max_length=32)
    device: str = Field(default="cpu", max_length=16)
    start_sec: float = Field(default=0.0, ge=0)
    end_sec: float | None = Field(default=None, gt=0)
    max_duration_sec: float | None = Field(default=None, ge=1, le=3600)
    processing_mode: str | None = Field(default=None, max_length=32)
    two_stems: str | None = Field(default=None, max_length=32)
    # Emit policy: confident (default) skips low-confidence Lead/Rhythm WAVs.
    lead_rhythm_mode: str = Field(default="confident", max_length=32)
    # Deprecated alias: True → best_effort for backward-compatible callers.
    lead_rhythm: bool = False
    dual_guitar: bool = False  # deprecated alias for lead_rhythm
    # Optional stage-1 guitar checkpoint when model is htdemucs_6s.
    guitar_checkpoint: str | None = Field(default=None, max_length=64)
    # Opt-in 4-stem then 6-stem residual pass (htdemucs_6s only).
    two_pass: bool = False
    # Opt-in MelBand guitar specialist refine pass.
    guitar_refine: bool = False
    low_end_restore_db: float = Field(default=0.0, ge=0.0, le=12.0)
    sub_bass_debleed: bool = False
    emit_stems: list[str] | None = Field(default=None)
    fold_other_into_guitar: bool = True
    fold_other_mode: str = Field(default="best_effort", max_length=32)

    @model_validator(mode="after")
    def _alias_dual_guitar(self) -> IsolateJobCreateRequest:
        if self.dual_guitar and not self.lead_rhythm:
            self.lead_rhythm = True
        if self.dual_guitar:
            self.lead_rhythm_mode = "best_effort"
        return self

    @field_validator("lead_rhythm_mode")
    @classmethod
    def _validate_lead_rhythm_mode(cls, v: str) -> str:
        mode = v.strip().lower()
        if mode not in ("confident", "best_effort"):
            raise ValueError("lead_rhythm_mode must be confident or best_effort")
        return mode

    @field_validator("fold_other_mode")
    @classmethod
    def _validate_fold_other_mode(cls, v: str) -> str:
        mode = (v or "best_effort").strip().lower()
        if mode not in ("full", "best_effort", "band_limited"):
            raise ValueError("fold_other_mode must be full|best_effort|band_limited")
        return mode

    @model_validator(mode="after")
    def _validate_region(self) -> IsolateJobCreateRequest:
        from audio_to_tab.isolate import MIN_REGION_SEC

        if self.end_sec is not None:
            if self.start_sec >= self.end_sec:
                raise ValueError("start_sec must be less than end_sec")
            length = self.end_sec - self.start_sec
            if length < MIN_REGION_SEC:
                raise ValueError(
                    f"region must be at least {MIN_REGION_SEC:.0f} seconds"
                )
        elif self.max_duration_sec is not None and self.max_duration_sec < MIN_REGION_SEC:
            raise ValueError(
                f"max_duration_sec must be at least {MIN_REGION_SEC:.0f} seconds when set"
            )
        return self


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
    kind: JobKind | None = None
