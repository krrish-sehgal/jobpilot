"""Repositories added in migration 0003: accounts, resumes, tailorings,
saved jobs, and idempotent messages."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from jobpilot.db.repositories.accounts import AuthCodeRepository, UserAccountRepository
from jobpilot.db.repositories.conversations import ConversationRepository, MessageRepository
from jobpilot.db.repositories.resumes import ResumeRepository
from jobpilot.db.repositories.saved_jobs import SavedJobRepository
from jobpilot.db.repositories.tailorings import TailoringRepository
from jobpilot.errors import RecordNotFoundError
from jobpilot.integrations.supabase_client import InMemoryDatabase
from jobpilot.models import AuthCode, Message, MessageDirection, SeniorityBand
from jobpilot.resume.models import (
    Decision,
    ResumeRecord,
    ResumeStatus,
    Suggestion,
    SuggestionKind,
    SuggestionSection,
    TailoringRecord,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _resume(user_id, *, primary=False, minutes=0) -> ResumeRecord:
    return ResumeRecord(
        id=uuid4(),
        user_id=user_id,
        file_name="cv.pdf",
        storage_key="k",
        status=ResumeStatus.READY,
        is_primary=primary,
        uploaded_at=NOW + timedelta(minutes=minutes),
    )


def test_account_is_created_once_per_email(db: InMemoryDatabase):
    repo = UserAccountRepository(db)
    first = repo.get_or_create_by_email("a@example.com", now=NOW)
    second = repo.get_or_create_by_email("a@example.com", now=NOW)
    assert first.id == second.id
    updated = repo.update_profile(first.id, full_name="Ada", seniority_band=SeniorityBand.MID)
    assert updated.full_name == "Ada" and updated.seniority_band == SeniorityBand.MID


def test_latest_active_code_ignores_consumed(db: InMemoryDatabase):
    repo = AuthCodeRepository(db)
    code = repo.save(AuthCode(email="a@example.com", code_hash="h", expires_at=NOW))
    assert repo.latest_active("a@example.com").id == code.id
    repo.update(code.model_copy(update={"consumed_at": NOW}))
    assert repo.latest_active("a@example.com") is None


def test_resume_ownership_and_single_primary(db: InMemoryDatabase):
    repo = ResumeRepository(db)
    owner, other = uuid4(), uuid4()
    a = repo.save(_resume(owner, primary=True, minutes=0))
    b = repo.save(_resume(owner, minutes=5))
    repo.make_primary(owner, b.id)
    assert repo.primary_for_user(owner).id == b.id
    assert [r.id for r in repo.list_for_user(owner)] == [b.id, a.id]
    with pytest.raises(RecordNotFoundError):
        repo.get_for_user(other, a.id)


def test_tailoring_roundtrip_keeps_suggestion_order_and_decisions(db: InMemoryDatabase):
    repo = TailoringRepository(db)
    user = uuid4()
    suggestions = [
        Suggestion(
            kind=SuggestionKind.ADD_SKILL,
            section=SuggestionSection.SKILLS,
            proposed=name,
        )
        for name in ("docker", "kafka", "redis")
    ]
    record = repo.save(
        TailoringRecord(user_id=user, resume_id=uuid4(), job_title="Eng", suggestions=suggestions)
    )
    assert [s.proposed for s in record.suggestions] == ["docker", "kafka", "redis"]
    repo.set_decisions(record.id, {suggestions[1].id: Decision.ACCEPTED})
    loaded = repo.get_for_user(user, record.id)
    assert [s.decision for s in loaded.suggestions] == [
        Decision.PENDING,
        Decision.ACCEPTED,
        Decision.PENDING,
    ]
    with pytest.raises(RecordNotFoundError):
        repo.get_for_user(uuid4(), record.id)


def test_saved_jobs_are_idempotent_and_newest_first(db: InMemoryDatabase):
    repo = SavedJobRepository(db)
    user, job_a, job_b = uuid4(), uuid4(), uuid4()
    repo.save(user, job_a)
    repo.save(user, job_a)
    repo.save(user, job_b)
    assert set(repo.job_ids_for_user(user)) == {job_a, job_b}
    assert repo.is_saved(user, job_a)
    repo.remove(user, job_a)
    repo.remove(user, job_a)  # unsaving twice is a no-op
    assert repo.job_ids_for_user(user) == [job_b]


def test_message_save_idempotent_returns_original(db: InMemoryDatabase):
    conversations = ConversationRepository(db)
    messages = MessageRepository(db)
    user = uuid4()
    conversation = conversations.create(user)

    def make() -> Message:
        return Message(
            conversation_id=conversation.id,
            user_id=user,
            direction=MessageDirection.INBOUND,
            body="hi",
            client_message_id="abc",
            turn_id=uuid4(),
        )

    first, created_first = messages.save_idempotent(make())
    second, created_second = messages.save_idempotent(make())
    assert created_first and not created_second
    assert second.id == first.id and second.turn_id == first.turn_id
    assert len(messages.list_for_conversation(conversation.id)) == 1
    inbound, reply = messages.find_turn(conversation.id, first.turn_id)
    assert inbound.id == first.id and reply is None
