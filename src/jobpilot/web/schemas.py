"""Request and response models for routes whose shape is not already a
domain model. Names and fields follow `docs/web-api.md` exactly."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from jobpilot.models import (
    EmploymentType,
    LocationTier,
    RoleCategory,
    SeniorityBand,
)
from jobpilot.resume.models import ResumeStatus

# --- auth -------------------------------------------------------------------


class RequestCodeBody(BaseModel):
    email: str = Field(max_length=254)


class VerifyCodeBody(BaseModel):
    email: str = Field(max_length=254)
    code: str = Field(max_length=16)


class SentResponse(BaseModel):
    sent: bool = True


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    seniority_band: SeniorityBand | None
    preferred_location_tiers: list[LocationTier]
    has_resume: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    expires_at: datetime
    user: UserOut


# --- jobs -------------------------------------------------------------------


class JobCardOut(BaseModel):
    job_id: str
    title: str
    company: str
    location_text: str | None
    location_tier: LocationTier
    seniority_band: SeniorityBand
    role_category: RoleCategory
    skills: list[str]
    description_preview: str
    compensation_text: str | None
    apply_url: str
    match_score: int  # 0-100
    match_reasons: list[str]
    posted_at: str | None
    is_saved: bool


class JobDetailOut(JobCardOut):
    description: str
    employment_type: EmploymentType
    min_years_experience: float


# --- chat -------------------------------------------------------------------


class ConversationSummaryOut(BaseModel):
    id: UUID
    title: str
    last_message_preview: str | None
    updated_at: datetime


class CreateConversationBody(BaseModel):
    """Accepts `{}`; any extra keys are ignored."""


class ChatMessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    body: str
    job_cards: list[JobCardOut]
    tailoring_id: UUID | None
    created_at: datetime


class PostMessageBody(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    client_message_id: str = Field(min_length=1, max_length=64)

    @field_validator("body")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value.strip()

    @field_validator("client_message_id")
    @classmethod
    def _is_uuid(cls, value: str) -> str:
        try:
            return str(UUID(value))
        except ValueError as exc:
            raise ValueError("client_message_id must be a UUID") from exc


class PostMessageResponse(BaseModel):
    message_id: UUID
    turn_id: UUID


# --- resumes and tailoring ----------------------------------------------------


class ResumeUploadResponse(BaseModel):
    resume_id: UUID
    status: Literal[ResumeStatus.PARSING] = ResumeStatus.PARSING


class TailoringCreateBody(BaseModel):
    resume_id: UUID
    job_id: UUID | None = None
    job_description_text: str | None = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def _exactly_one_job_source(self) -> TailoringCreateBody:
        has_text = bool(self.job_description_text and self.job_description_text.strip())
        if (self.job_id is None) == (not has_text):
            raise ValueError("provide exactly one of job_id or job_description_text")
        return self


class TailoringCreateResponse(BaseModel):
    tailoring_id: UUID
    status: Literal["running"] = "running"


class DecisionsBody(BaseModel):
    accepted: list[UUID] = Field(default_factory=list, max_length=100)
    rejected: list[UUID] = Field(default_factory=list, max_length=100)
