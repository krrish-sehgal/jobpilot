"""Dependency wiring for the web service.

`WebContainer` is the one place that knows how the pieces fit: which
database, which LLM, which storage, which repositories feed which
services. `create_web_app` builds it once; routes receive it through
FastAPI's dependency injection and never construct collaborators
themselves. Tests build a container over the in-memory fakes and pass
it in, so no route test touches real infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from jobpilot.agent.loop import AgentLoop
from jobpilot.agent.registry import build_default_registry
from jobpilot.agent.tools import AgentToolContext
from jobpilot.chat.ledger import DeliveryLedger
from jobpilot.chat.orchestrator import TurnOrchestrator
from jobpilot.config import Settings
from jobpilot.db.client import get_database
from jobpilot.db.repositories.accounts import AuthCodeRepository, UserAccountRepository
from jobpilot.db.repositories.conversations import (
    ConversationRepository,
    MessageRepository,
    OutboundDeliveryRepository,
    TurnLeaseRepository,
)
from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.db.repositories.resumes import ResumeRepository
from jobpilot.db.repositories.saved_jobs import SavedJobRepository
from jobpilot.db.repositories.tailorings import TailoringRepository
from jobpilot.db.repositories.users import UserFactRepository
from jobpilot.errors import InvalidTokenError, RecordNotFoundError
from jobpilot.integrations.llm import FakeLLMClient, HTTPLLMClient, LLMClient
from jobpilot.integrations.storage import HTTPObjectStorage, InMemoryObjectStorage, ObjectStorage
from jobpilot.integrations.supabase_client import Database, InMemoryDatabase
from jobpilot.memory.store import MemoryStore
from jobpilot.models import UserAccount
from jobpilot.resume.extract import TextExtractor
from jobpilot.resume.models import ResumeSections
from jobpilot.resume.render import DocumentRenderer
from jobpilot.resume.scoring import candidate_band
from jobpilot.resume.service import ResumeService, Scheduler, ServiceResumeFetcher, run_in_thread
from jobpilot.web.auth import AuthService, CodeSender, LoggingCodeSender, TokenSigner
from jobpilot.web.presenters import ConversationPresenter, JobPresenter
from jobpilot.web.streaming import TurnStreamer

_PLACEHOLDER_SUPABASE = "your-project.supabase.co"


def _is_local(settings: Settings) -> bool:
    return settings.environment in {"development", "test"}


@dataclass
class WebContainer:
    settings: Settings
    llm: LLMClient
    users: UserAccountRepository
    conversations: ConversationRepository
    messages: MessageRepository
    jobs: JobRepository
    saved_jobs: SavedJobRepository
    memory: MemoryStore
    signer: TokenSigner
    auth: AuthService
    resume_service: ResumeService
    streamer: TurnStreamer
    jobs_presenter: JobPresenter
    conversations_presenter: ConversationPresenter

    def tool_context(self, user: UserAccount, conversation_id: UUID) -> AgentToolContext:
        """The per-turn tool context: who is asking, and what they can use."""

        return AgentToolContext(
            user_id=user.id,
            conversation_id=conversation_id,
            llm=self.llm,
            job_repository=self.jobs,
            memory_store=self.memory,
            resume_fetcher=ServiceResumeFetcher(self.resume_service),
            candidate_seniority=user.seniority_band,
            preferred_location_tiers=user.preferred_location_tiers or None,
            saved_job_ids={str(j) for j in self.saved_jobs.job_ids_for_user(user.id)},
            tailoring_launcher=self.resume_service,
        )


def build_container(
    settings: Settings,
    *,
    db: Database | None = None,
    llm: LLMClient | None = None,
    storage: ObjectStorage | None = None,
    code_sender: CodeSender | None = None,
    extractor: TextExtractor | None = None,
    renderer: DocumentRenderer | None = None,
    scheduler: Scheduler = run_in_thread,
) -> WebContainer:
    """Assemble the service graph. Every external boundary can be overridden.

    With nothing overridden and placeholder credentials in a local
    environment, it falls back to the in-memory fakes so `make run-web`
    starts without any infrastructure.
    """

    if db is None:
        placeholder = settings.supabase_url.endswith(_PLACEHOLDER_SUPABASE)
        db = InMemoryDatabase() if _is_local(settings) and placeholder else get_database(settings)
    if llm is None:
        llm = FakeLLMClient() if settings.llm_provider == "fake" else HTTPLLMClient(settings)
    if storage is None:
        local = _is_local(settings) and settings.object_storage_access_key.startswith(
            "replace-with"
        )
        storage = InMemoryObjectStorage() if local else HTTPObjectStorage(settings)

    users = UserAccountRepository(db)
    messages = MessageRepository(db)
    jobs = JobRepository(db)
    saved = SavedJobRepository(db)
    resumes = ResumeRepository(db)

    def on_resume_ready(user_id: UUID, sections: ResumeSections) -> None:
        # Fill the profile from the resume the first time, without ever
        # overwriting something the user (or an earlier resume) set.
        account = users.get(user_id)
        users.update_profile(
            user_id,
            full_name=None if account.full_name else (sections.contact.name or None),
            seniority_band=None if account.seniority_band else candidate_band(sections),
        )

    resume_service = ResumeService(
        resumes=resumes,
        tailorings=TailoringRepository(db),
        jobs=jobs,
        storage=storage,
        llm=llm,
        extractor=extractor,
        renderer=renderer,
        max_bytes=settings.resume_max_bytes,
        schedule=scheduler,
        on_resume_ready=on_resume_ready,
    )
    orchestrator = TurnOrchestrator(
        messages=messages,
        leases=TurnLeaseRepository(db),
        ledger=DeliveryLedger(OutboundDeliveryRepository(db)),
        agent_loop=AgentLoop(
            llm=llm,
            registry=build_default_registry(),
            max_turns=settings.agent_max_turns,
            max_tool_calls_per_turn=settings.agent_max_tool_calls_per_turn,
        ),
        lease_seconds=settings.turn_lease_seconds,
        worker_id="web-1",
    )
    signer = TokenSigner(settings.auth_token_secret, timedelta(hours=settings.auth_token_ttl_hours))
    container = WebContainer(
        settings=settings,
        llm=llm,
        users=users,
        conversations=ConversationRepository(db),
        messages=messages,
        jobs=jobs,
        saved_jobs=saved,
        memory=MemoryStore(llm, UserFactRepository(db)),
        signer=signer,
        auth=AuthService(
            accounts=users,
            codes=AuthCodeRepository(db),
            signer=signer,
            sender=code_sender or LoggingCodeSender(log_code=settings.environment != "production"),
            secret=settings.auth_token_secret,
        ),
        resume_service=resume_service,
        streamer=None,  # type: ignore[arg-type]  # set just below; needs `container.tool_context`
        jobs_presenter=JobPresenter(jobs=jobs, saved=saved, resumes=resumes, llm=llm),
        conversations_presenter=ConversationPresenter(messages, saved),
    )
    container.streamer = TurnStreamer(
        messages=messages, orchestrator=orchestrator, context_factory=container.tool_context
    )
    return container


# --- FastAPI dependencies ---------------------------------------------------


def get_container(request: Request) -> WebContainer:
    return request.app.state.container


Container = Annotated[WebContainer, Depends(get_container)]


def current_user(request: Request, container: Container) -> UserAccount:
    """Resolve the bearer token to a user, or raise (-> 401 `unauthorized`).

    A valid token for a user that no longer exists is treated the same as
    an invalid token: the caller cannot tell the difference.
    """

    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise InvalidTokenError("missing bearer token")
    user_id = container.signer.verify(token.strip())
    try:
        return container.users.get(user_id)
    except RecordNotFoundError as exc:
        raise InvalidTokenError("unknown user") from exc


CurrentUser = Annotated[UserAccount, Depends(current_user)]


def parse_id(value: str) -> UUID:
    """Path ids that are not UUIDs are simply "not found", not a 422."""

    try:
        return UUID(value)
    except ValueError as exc:
        raise RecordNotFoundError(f"bad id {value!r}") from exc
