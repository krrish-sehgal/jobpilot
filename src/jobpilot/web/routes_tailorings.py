"""`/tailorings/*`: start, poll, decide, export."""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Query, Response

from jobpilot.resume.models import Tailoring
from jobpilot.resume.render import DocumentFormat
from jobpilot.web.deps import Container, CurrentUser, parse_id
from jobpilot.web.schemas import DecisionsBody, TailoringCreateBody, TailoringCreateResponse

router = APIRouter(tags=["tailoring"])


@router.post("/tailorings", status_code=202)
def create_tailoring(
    body: TailoringCreateBody, container: Container, user: CurrentUser
) -> TailoringCreateResponse:
    record = container.resume_service.start_tailoring(
        user.id,
        body.resume_id,
        job_id=body.job_id,
        job_description_text=body.job_description_text,
    )
    return TailoringCreateResponse(tailoring_id=record.id)


@router.get("/tailorings/{tailoring_id}")
def get_tailoring(tailoring_id: str, container: Container, user: CurrentUser) -> Tailoring:
    return container.resume_service.get_tailoring(user.id, parse_id(tailoring_id)).to_public()


@router.post("/tailorings/{tailoring_id}/decisions")
def decide(
    tailoring_id: str, body: DecisionsBody, container: Container, user: CurrentUser
) -> Tailoring:
    record = container.resume_service.decide(
        user.id, parse_id(tailoring_id), accepted=body.accepted, rejected=body.rejected
    )
    return record.to_public()


@router.get("/tailorings/{tailoring_id}/export")
def export_tailoring(
    tailoring_id: str,
    container: Container,
    user: CurrentUser,
    format: Literal["pdf", "docx"] = Query(...),
) -> Response:
    document, file_name = container.resume_service.export(
        user.id, parse_id(tailoring_id), DocumentFormat(format)
    )
    return Response(
        content=document.content,
        media_type=document.media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}"},
    )
