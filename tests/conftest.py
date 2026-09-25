from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from jobpilot.db.repositories.conversations import (
    MessageRepository,
    OutboundDeliveryRepository,
    TurnLeaseRepository,
)
from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.db.repositories.users import UserFactRepository
from jobpilot.integrations.llm import FakeLLMClient
from jobpilot.integrations.queue_backend import InMemoryQueueBackend
from jobpilot.integrations.storage import InMemoryObjectStorage
from jobpilot.integrations.supabase_client import InMemoryDatabase
from jobpilot.models import (
    CompensationRange,
    EmploymentType,
    FraudSignal,
    JobRecord,
    LocationTier,
    RoleCategory,
    SeniorityBand,
)


@pytest.fixture
def db() -> InMemoryDatabase:
    return InMemoryDatabase()


@pytest.fixture
def job_repository(db: InMemoryDatabase) -> JobRepository:
    return JobRepository(db)


@pytest.fixture
def message_repository(db: InMemoryDatabase) -> MessageRepository:
    return MessageRepository(db)


@pytest.fixture
def lease_repository(db: InMemoryDatabase) -> TurnLeaseRepository:
    return TurnLeaseRepository(db)


@pytest.fixture
def delivery_repository(db: InMemoryDatabase) -> OutboundDeliveryRepository:
    return OutboundDeliveryRepository(db)


@pytest.fixture
def user_fact_repository(db: InMemoryDatabase) -> UserFactRepository:
    return UserFactRepository(db)


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def queue_backend() -> InMemoryQueueBackend:
    return InMemoryQueueBackend(visibility_timeout_seconds=5, max_receive_count=3)


@pytest.fixture
def object_storage() -> InMemoryObjectStorage:
    return InMemoryObjectStorage()


def make_job_record(
    *,
    title: str = "Senior Backend Engineer",
    company: str = "Acme Corp",
    role_category: RoleCategory = RoleCategory.SOFTWARE_ENGINEERING,
    seniority_band: SeniorityBand = SeniorityBand.SENIOR,
    min_years_experience: float = 5,
    skills: list[str] | None = None,
    location_tier: LocationTier = LocationTier.REMOTE,
    posted_at: datetime | None = None,
    compensation: CompensationRange | None = None,
    fraud_signal: FraudSignal = FraudSignal.NONE,
    candidate_profile_text: str = (
        "Has 5+ years building backend systems in Python and Go, comfortable "
        "owning a service end to end and mentoring junior engineers."
    ),
) -> JobRecord:
    return JobRecord(
        source_platform="talentflow",
        source_listing_id=str(uuid4()),
        content_hash=str(uuid4()).replace("-", ""),
        title=title,
        company=company,
        description="A" * 250,
        apply_url="https://apply.example.com/job/123",
        role_category=role_category,
        seniority_band=seniority_band,
        min_years_experience=min_years_experience,
        skills=skills or ["python", "go"],
        location_text="Remote",
        location_tier=location_tier,
        employment_type=EmploymentType.FULL_TIME,
        compensation=compensation,
        fraud_signal=fraud_signal,
        candidate_profile_text=candidate_profile_text,
        posted_at=posted_at or (datetime.now(UTC) - timedelta(days=1)),
    )
