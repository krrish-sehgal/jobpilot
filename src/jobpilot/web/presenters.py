"""Shaping domain objects into what the website renders.

Presenters hold the small bits of read-side logic that do not belong in
a route (a score for a job the user did not search for, the sidebar
preview text) and that more than one route needs.
"""

from __future__ import annotations

from collections.abc import Collection

from jobpilot.chat.cards import render_job_card
from jobpilot.db.repositories.conversations import MessageRepository
from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.db.repositories.resumes import ResumeRepository
from jobpilot.db.repositories.saved_jobs import SavedJobRepository
from jobpilot.integrations.llm import LLMClient
from jobpilot.models import (
    Conversation,
    JobRecord,
    Message,
    MessageDirection,
    UserAccount,
)
from jobpilot.search.embed import cosine_similarity
from jobpilot.search.ranking import score_job
from jobpilot.web.schemas import ChatMessageOut, ConversationSummaryOut, JobCardOut, JobDetailOut

_PREVIEW_CHARS = 80
_RESUME_EMBED_CHARS = 4000
#: Used when there is no resume to compare against: the same neutral value
#: `search.ranking` uses for "unknown", so such a job is neither favoured
#: nor penalised on semantic fit.
_NEUTRAL_SIMILARITY = 0.5


class JobPresenter:
    """Builds cards and details for the signed-in user."""

    def __init__(
        self,
        *,
        jobs: JobRepository,
        saved: SavedJobRepository,
        resumes: ResumeRepository,
        llm: LLMClient,
    ) -> None:
        self._jobs = jobs
        self._saved = saved
        self._resumes = resumes
        self._llm = llm

    def card(
        self, user: UserAccount, job: JobRecord, *, saved_ids: Collection[str] | None = None
    ) -> JobCardOut:
        if saved_ids is None:
            saved_ids = {str(j) for j in self._saved.job_ids_for_user(user.id)}
        scored = score_job(
            job,
            semantic_similarity=self._similarity(user, job),
            candidate_seniority=user.seniority_band,
            preferred_location_tiers=user.preferred_location_tiers or None,
        )
        return JobCardOut.model_validate(
            render_job_card(
                scored,
                candidate_seniority=user.seniority_band,
                preferred_location_tiers=user.preferred_location_tiers or None,
                saved_job_ids=saved_ids,
            )
        )

    def detail(self, user: UserAccount, job: JobRecord) -> JobDetailOut:
        card = self.card(user, job)
        return JobDetailOut(
            **card.model_dump(),
            description=job.description,
            employment_type=job.employment_type,
            min_years_experience=job.min_years_experience,
        )

    def _similarity(self, user: UserAccount, job: JobRecord) -> float:
        """Semantic fit between the user's primary resume and the job.

        Embeds on demand; a production deployment would read the job's
        stored `candidate_profile_embedding` and cache the resume's.
        """

        primary = self._resumes.primary_for_user(user.id)
        if primary is None or not primary.raw_text:
            return _NEUTRAL_SIMILARITY
        resume_vector, job_vector = self._llm.embed(
            [primary.raw_text[:_RESUME_EMBED_CHARS], job.candidate_profile_text]
        )
        return cosine_similarity(resume_vector, job_vector)


class ConversationPresenter:
    def __init__(self, messages: MessageRepository, saved: SavedJobRepository) -> None:
        self._messages = messages
        self._saved = saved

    def summary(self, conversation: Conversation) -> ConversationSummaryOut:
        history = self._messages.list_for_conversation(conversation.id)
        preview = None
        if history:
            text = " ".join(history[-1].body.split())
            preview = text if len(text) <= _PREVIEW_CHARS else text[: _PREVIEW_CHARS - 1] + "…"
        return ConversationSummaryOut(
            id=conversation.id,
            title=conversation.title,
            last_message_preview=preview,
            updated_at=conversation.updated_at,
        )

    def message(self, message: Message, *, saved_ids: Collection[str]) -> ChatMessageOut:
        """A stored message as the website sees it.

        `is_saved` on stored cards is refreshed at read time: the card was
        a snapshot from when the reply was written, and the user may have
        saved or unsaved the job since.
        """

        cards = [
            {**card, "is_saved": card.get("job_id") in saved_ids} for card in message.job_cards
        ]
        return ChatMessageOut(
            id=message.id,
            role="user" if message.direction is MessageDirection.INBOUND else "assistant",
            body=message.body,
            job_cards=[JobCardOut.model_validate(c) for c in cards],
            tailoring_id=message.tailoring_id,
            created_at=message.created_at,
        )

    def messages(self, conversation: Conversation, user: UserAccount) -> list[ChatMessageOut]:
        saved_ids = {str(j) for j in self._saved.job_ids_for_user(user.id)}
        return [
            self.message(m, saved_ids=saved_ids)
            for m in self._messages.list_for_conversation(conversation.id)
        ]
