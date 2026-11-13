"""`/jobs/{id}`, save/unsave, and `/saved-jobs`."""

from __future__ import annotations

from fastapi import APIRouter, Response

from jobpilot.errors import RecordNotFoundError
from jobpilot.web.deps import Container, CurrentUser, parse_id
from jobpilot.web.schemas import JobCardOut, JobDetailOut

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
def get_job(job_id: str, container: Container, user: CurrentUser) -> JobDetailOut:
    job = container.jobs.get(parse_id(job_id))
    return container.jobs_presenter.detail(user, job)


@router.post("/jobs/{job_id}/save", status_code=204)
def save_job(job_id: str, container: Container, user: CurrentUser) -> Response:
    job = container.jobs.get(parse_id(job_id))  # 404 for a job that does not exist
    container.saved_jobs.save(user.id, job.id)
    return Response(status_code=204)


@router.delete("/jobs/{job_id}/save", status_code=204)
def unsave_job(job_id: str, container: Container, user: CurrentUser) -> Response:
    container.saved_jobs.remove(user.id, parse_id(job_id))
    return Response(status_code=204)


@router.get("/saved-jobs")
def list_saved_jobs(container: Container, user: CurrentUser) -> list[JobCardOut]:
    saved_ids = container.saved_jobs.job_ids_for_user(user.id)
    id_set = {str(j) for j in saved_ids}
    cards = []
    for job_id in saved_ids:
        try:
            cards.append(
                container.jobs_presenter.card(user, container.jobs.get(job_id), saved_ids=id_set)
            )
        except RecordNotFoundError:  # a job deleted after it was saved is skipped, not fatal
            continue
    return cards
