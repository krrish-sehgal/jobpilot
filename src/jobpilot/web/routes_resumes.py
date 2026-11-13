"""`/resumes/*`: upload, list, fetch, choose primary."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from jobpilot.resume.models import Resume, ResumeSummary
from jobpilot.web.deps import Container, CurrentUser, parse_id
from jobpilot.web.schemas import ResumeUploadResponse

router = APIRouter(tags=["resumes"])


@router.post("/resumes", status_code=202)
async def upload_resume(
    file: Annotated[UploadFile, File()], container: Container, user: CurrentUser
) -> ResumeUploadResponse:
    """Accept a PDF or DOCX and start parsing it in the background.

    At most `limit + 1` bytes are read: enough to know the file is too
    large, without buffering an arbitrarily large body in memory. Size
    and type are validated by the service, which raises the contract's
    `file_too_large` / `unsupported_file_type` errors.
    """

    limit = container.settings.resume_max_bytes
    data = await file.read(limit + 1)
    record = await run_in_threadpool(
        container.resume_service.upload, user.id, file.filename or "resume", data
    )
    return ResumeUploadResponse(resume_id=record.id)


@router.get("/resumes")
def list_resumes(container: Container, user: CurrentUser) -> list[ResumeSummary]:
    return [r.to_summary() for r in container.resume_service.list_resumes(user.id)]


@router.get("/resumes/{resume_id}")
def get_resume(resume_id: str, container: Container, user: CurrentUser) -> Resume:
    return container.resume_service.get_resume(user.id, parse_id(resume_id)).to_public()


@router.post("/resumes/{resume_id}/primary", status_code=204)
def make_primary(resume_id: str, container: Container, user: CurrentUser) -> Response:
    container.resume_service.set_primary(user.id, parse_id(resume_id))
    return Response(status_code=204)
