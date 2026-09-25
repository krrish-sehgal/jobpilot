"""Typed domain models and the JobPilot role/seniority taxonomy.

These are the shapes that flow between layers: a scraper produces a
`RawPosting`, enrichment turns that into a `JobRecord`, search returns
`ScoredJob` results, and chat exchanges `Message` / `AgentTurn` objects.
Everything here is a `pydantic.BaseModel`, so invalid data fails fast
at the boundary where it enters the system rather than propagating
silently downstream.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


class RoleCategory(StrEnum):
    """The eight role categories JobPilot classifies postings into.

    This taxonomy is intentionally small and mutually exclusive at the
    top level — a posting is assigned exactly one category. Anything
    that doesn't cleanly fit falls to `OTHER` rather than forcing a
    bad match, so downstream ranking never silently trusts a wrong
    category.
    """

    SOFTWARE_ENGINEERING = "software_engineering"
    DATA_AND_ANALYTICS = "data_and_analytics"
    PRODUCT_AND_DESIGN = "product_and_design"
    SALES_AND_BUSINESS_DEV = "sales_and_business_dev"
    MARKETING_AND_GROWTH = "marketing_and_growth"
    OPERATIONS_AND_SUPPORT = "operations_and_support"
    FINANCE_AND_LEGAL = "finance_and_legal"
    OTHER = "other"


class SeniorityBand(StrEnum):
    """The five seniority bands, each mapped to a year-of-experience range.

    Bands are ordinal (INTERN < ENTRY < ... < LEADERSHIP) — ranking and
    seniority-fit scoring rely on `SENIORITY_ORDER` below rather than
    string comparison.
    """

    INTERN = "intern"
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEADERSHIP = "leadership"


#: Inclusive (min_years, max_years) band for each seniority level.
#: `max_years` of `None` means "no upper bound".
SENIORITY_YEAR_RANGES: dict[SeniorityBand, tuple[int, int | None]] = {
    SeniorityBand.INTERN: (0, 0),
    SeniorityBand.ENTRY: (0, 2),
    SeniorityBand.MID: (2, 5),
    SeniorityBand.SENIOR: (5, 10),
    SeniorityBand.LEADERSHIP: (10, None),
}

#: Ordinal rank for each band, used by seniority-fit scoring in
#: `jobpilot.search.ranking`. Lower is more junior.
SENIORITY_ORDER: dict[SeniorityBand, int] = {
    SeniorityBand.INTERN: 0,
    SeniorityBand.ENTRY: 1,
    SeniorityBand.MID: 2,
    SeniorityBand.SENIOR: 3,
    SeniorityBand.LEADERSHIP: 4,
}


def seniority_band_for_years(years: float) -> SeniorityBand:
    """Map a raw years-of-experience number onto a `SeniorityBand`.

    `INTERN` is deliberately excluded from this mapping: both
    `intern` and `entry` cover 0 years, and the two are distinguished
    by whether a posting is explicitly an internship, not by years
    alone. A years-only mapping of 0 always resolves to `ENTRY`;
    callers that need to validate an explicit `INTERN` posting should
    check `years == 0` directly rather than relying on this function.

    Uses the inclusive lower bound of each of the remaining ranges; a
    value that lands exactly on a boundary (e.g. 2.0 years) resolves
    to the *more senior* band, since job postings phrased as "2+
    years" typically mean the role has grown past pure entry-level
    scope.
    """

    if years < 0:
        raise ValueError("years of experience cannot be negative")
    band = SeniorityBand.ENTRY
    for candidate, (lo, _hi) in SENIORITY_YEAR_RANGES.items():
        if candidate == SeniorityBand.INTERN:
            continue
        if years >= lo:
            band = candidate
    return band


class LocationTier(StrEnum):
    """Coarse location classification used for filtering and scoring."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class FraudSignal(StrEnum):
    """Outcome of the enrichment fraud-signal check on a posting."""

    NONE = "none"
    SUSPICIOUS = "suspicious"
    LIKELY_SCAM = "likely_scam"


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


class RawPosting(BaseModel):
    """Unprocessed output of a scraper, before enrichment.

    `content_hash` is computed by `jobpilot.utils.hashing.content_hash`
    over the normalized `(title, company, description)` tuple and is
    the dedup key used across a scraper restart or a re-crawl of the
    same listing.
    """

    model_config = ConfigDict(frozen=True)

    source_platform: str
    source_listing_id: str
    title: str
    company: str
    description: str
    location_text: str | None = None
    posted_at: datetime | None = None
    apply_url: str
    content_hash: str
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("title", "company", "description", "apply_url")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be blank")
        return value.strip()


class IngestCheckpoint(BaseModel):
    """Resume state for a single scraper run against a single platform."""

    source_platform: str
    cursor: str | None = None
    last_run_started_at: datetime | None = None
    last_run_completed_at: datetime | None = None
    postings_seen: int = 0
    postings_new: int = 0
    postings_duplicate: int = 0


# ---------------------------------------------------------------------------
# Enrichment / JobRecord
# ---------------------------------------------------------------------------


class CompensationRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    currency: str = Field(default="USD", min_length=3, max_length=3)
    min_amount: float | None = Field(default=None, ge=0)
    max_amount: float | None = Field(default=None, ge=0)
    period: str = Field(default="year", description="year | month | hour")

    @model_validator(mode="after")
    def _min_le_max(self) -> CompensationRange:
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount > self.max_amount
        ):
            raise ValueError("min_amount cannot exceed max_amount")
        return self


class JobRecord(BaseModel):
    """A posting after LLM enrichment: a strict, taxonomy-validated record.

    This is the canonical shape stored in the `jobs` table and served
    by search. `candidate_profile_text` is the field the matching
    engine actually embeds — see `jobpilot.ingest.enrich` and
    `docs/architecture.md` for why.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    source_platform: str
    source_listing_id: str
    content_hash: str
    title: str
    company: str
    description: str
    apply_url: str

    role_category: RoleCategory
    seniority_band: SeniorityBand
    min_years_experience: float = Field(ge=0)
    skills: list[str] = Field(default_factory=list)
    location_text: str | None = None
    location_tier: LocationTier = LocationTier.UNKNOWN
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    compensation: CompensationRange | None = None
    fraud_signal: FraudSignal = FraudSignal.NONE
    fraud_signal_reason: str | None = None

    candidate_profile_text: str = Field(
        min_length=1,
        description="LLM-authored description of the ideal candidate; this is what gets embedded.",
    )

    posted_at: datetime | None = None
    enriched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("skills")
    @classmethod
    def _dedupe_and_lower(cls, value: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for skill in value:
            normalized = skill.strip().lower()
            if normalized and normalized not in seen:
                seen[normalized] = None
        return list(seen.keys())

    @model_validator(mode="after")
    def _seniority_years_consistent(self) -> JobRecord:
        if self.seniority_band == SeniorityBand.INTERN:
            if self.min_years_experience != 0:
                raise ValueError(
                    "seniority_band='intern' requires min_years_experience == 0, "
                    f"got {self.min_years_experience!r}"
                )
            return self

        expected = seniority_band_for_years(self.min_years_experience)
        if expected != self.seniority_band:
            raise ValueError(
                f"seniority_band={self.seniority_band!r} is inconsistent with "
                f"min_years_experience={self.min_years_experience!r} "
                f"(expected {expected!r})"
            )
        return self


class EnrichmentRequest(BaseModel):
    """Input to the enrichment LLM call: a `RawPosting` plus context."""

    model_config = ConfigDict(frozen=True)

    raw_posting: RawPosting


# ---------------------------------------------------------------------------
# Users, memory, search
# ---------------------------------------------------------------------------


class UserFact(BaseModel):
    """A durable fact extracted from conversation history about a user."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    fact_text: str = Field(min_length=1)
    category: str = Field(
        default="general",
        description="e.g. preference, constraint, background, goal",
    )
    confidence: float = Field(default=0.8, ge=0, le=1)
    source_message_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    superseded_by: UUID | None = None


class SearchFilters(BaseModel):
    """Structured hard filters applied alongside semantic similarity."""

    role_categories: list[RoleCategory] = Field(default_factory=list)
    seniority_bands: list[SeniorityBand] = Field(default_factory=list)
    location_tiers: list[LocationTier] = Field(default_factory=list)
    employment_types: list[EmploymentType] = Field(default_factory=list)
    min_compensation: float | None = Field(default=None, ge=0)
    max_years_experience: float | None = Field(default=None, ge=0)
    exclude_fraud_signals: list[FraudSignal] = Field(
        default_factory=lambda: [FraudSignal.LIKELY_SCAM]
    )


class ScoredJob(BaseModel):
    """A job record with its ranking signals and combined score."""

    job: JobRecord
    semantic_similarity: float = Field(ge=0, le=1)
    recency_score: float = Field(ge=0, le=1)
    seniority_fit_score: float = Field(ge=0, le=1)
    location_fit_score: float = Field(ge=0, le=1)
    completeness_score: float = Field(ge=0, le=1)
    combined_score: float = Field(ge=0, le=1)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    user_id: UUID
    direction: MessageDirection
    body: str
    status: MessageStatus = MessageStatus.RECEIVED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TurnLease(BaseModel):
    """A claim-and-lease record preventing double-processing of a turn."""

    conversation_id: UUID
    worker_id: str
    claimed_at: datetime
    expires_at: datetime


class OutboundDelivery(BaseModel):
    """A ledger row for an outbound message, keyed by idempotency key."""

    id: UUID = Field(default_factory=uuid4)
    idempotency_key: str
    conversation_id: UUID
    body: str
    delivered_at: datetime | None = None


class ToolCall(BaseModel):
    """A single tool invocation the agent loop made during a turn."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: str | None = None


class AgentTurn(BaseModel):
    """The full record of one agent loop execution for a single message."""

    conversation_id: UUID
    user_message: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    final_reply: str | None = None
    turns_used: int = 0
    completed: bool = False
