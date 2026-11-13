"""The web service application factory.

    uvicorn jobpilot.web.app:create_web_app --factory --port 8001

(`make run-web`). All routes live under `/api/v1`, per `docs/web-api.md`.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobpilot.config import Settings, get_settings
from jobpilot.errors import ConfigurationError
from jobpilot.logging import get_logger
from jobpilot.web import routes_auth, routes_chat, routes_jobs, routes_resumes, routes_tailorings
from jobpilot.web.deps import WebContainer, build_container
from jobpilot.web.errors import install_error_handlers

logger = get_logger(__name__)

API_PREFIX = "/api/v1"


def _check_secrets(settings: Settings) -> None:
    """Refuse to start a non-local deployment that signs tokens with a placeholder."""

    if not settings.auth_secret_is_placeholder:
        return
    if settings.environment in {"development", "test"}:
        logger.warning("auth_token_secret_is_placeholder", environment=settings.environment)
        return
    raise ConfigurationError(
        "JOBPILOT_AUTH_TOKEN_SECRET must be set to a secret value outside development"
    )


def create_web_app(
    settings: Settings | None = None, *, container: WebContainer | None = None
) -> FastAPI:
    """Build the FastAPI app.

    Pass `container` to supply pre-built dependencies (tests do, with the
    in-memory test doubles); otherwise one is built from `settings`.
    """

    settings = settings or (container.settings if container else get_settings())
    if container is None:
        _check_secrets(settings)
        container = build_container(settings)

    app = FastAPI(title="JobPilot Web API", version="1.0.0")
    app.state.container = container

    # Browsers send credentials as an Authorization header, not cookies, so
    # `allow_credentials` stays off and only the configured origins may call.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.web_allowed_origins_list,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
    )
    install_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)

    @api.get("/healthz", tags=["ops"])
    def healthz() -> dict:
        return {"status": "ok"}

    for module in (routes_auth, routes_chat, routes_jobs, routes_resumes, routes_tailorings):
        api.include_router(module.router)
    app.include_router(api)
    return app
