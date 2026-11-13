"""`/auth/*` and `/me`."""

from __future__ import annotations

from fastapi import APIRouter

from jobpilot.models import UserAccount
from jobpilot.web.deps import Container, CurrentUser
from jobpilot.web.schemas import (
    RequestCodeBody,
    SentResponse,
    TokenResponse,
    UserOut,
    VerifyCodeBody,
)

router = APIRouter(tags=["auth"])


def user_out(container: Container, user: UserAccount) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        seniority_band=user.seniority_band,
        preferred_location_tiers=user.preferred_location_tiers,
        has_resume=container.resume_service.has_resume(user.id),
        created_at=user.created_at,
    )


@router.post("/auth/request-code", status_code=202)
def request_code(body: RequestCodeBody, container: Container) -> SentResponse:
    # Always `sent: true` for a well-formed email, whether or not an account
    # exists, so this endpoint cannot be used to enumerate users.
    container.auth.request_code(body.email)
    return SentResponse()


@router.post("/auth/verify-code")
def verify_code(body: VerifyCodeBody, container: Container) -> TokenResponse:
    token, expires_at, user = container.auth.verify_code(body.email, body.code)
    return TokenResponse(access_token=token, expires_at=expires_at, user=user_out(container, user))


@router.get("/me")
def me(container: Container, user: CurrentUser) -> UserOut:
    return user_out(container, user)
