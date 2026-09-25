"""Exception hierarchy for JobPilot.

Every exception the application raises deliberately (as opposed to
letting a third-party library's own exception surface) should be a
subclass of `JobPilotError`. This lets callers at a service boundary
(the webhook handler, the worker loop) catch one base type and decide
how to translate it into an HTTP response or a retry decision, instead
of enumerating every possible library exception.
"""

from __future__ import annotations


class JobPilotError(Exception):
    """Base class for all application-raised errors."""


# --- Configuration -----------------------------------------------------


class ConfigurationError(JobPilotError):
    """Raised when required configuration is missing or invalid."""


# --- Domain validation ---------------------------------------------------


class ValidationError(JobPilotError):
    """A domain object failed validation against business rules.

    Distinct from `pydantic.ValidationError`, which is a schema-level
    failure. This is raised for rule-level failures, e.g. an
    enrichment record referencing a role category outside the
    taxonomy.
    """


class TaxonomyError(ValidationError):
    """A value was not found in the JobPilot role/seniority taxonomy."""


# --- Ingestion -------------------------------------------------------------


class ScraperError(JobPilotError):
    """Base class for scraper failures."""


class ScraperRateLimitedError(ScraperError):
    """The upstream ATS platform rate-limited or throttled a scraper."""


class ScraperParseError(ScraperError):
    """A scraper could not parse a listing page into structured data."""


class DuplicatePostingError(JobPilotError):
    """A posting with an identical content hash already exists."""

    def __init__(self, content_hash: str, existing_job_id: str | None = None) -> None:
        self.content_hash = content_hash
        self.existing_job_id = existing_job_id
        super().__init__(
            f"duplicate posting content_hash={content_hash!r} existing_job_id={existing_job_id!r}"
        )


class CheckpointError(JobPilotError):
    """Raised when checkpoint state could not be read or written."""


# --- Enrichment --------------------------------------------------------


class EnrichmentError(JobPilotError):
    """Base class for LLM enrichment failures."""


class EnrichmentSchemaError(EnrichmentError):
    """The LLM's enrichment output failed strict schema validation."""


# --- Search ------------------------------------------------------------


class SearchError(JobPilotError):
    """Base class for search and ranking failures."""


class RankingWeightError(SearchError):
    """Ranking signal weights are misconfigured (e.g. do not sum to 1)."""


# --- Chat / orchestration -----------------------------------------------


class ChatError(JobPilotError):
    """Base class for chat pipeline failures."""


class SignatureVerificationError(ChatError):
    """An inbound webhook payload failed signature verification."""


class TurnLeaseConflictError(ChatError):
    """Another worker already holds the lease for this conversation turn."""


class TurnBudgetExceededError(ChatError):
    """The agent loop exceeded its configured turn or tool-call budget."""


class DuplicateDeliveryError(ChatError):
    """An outbound message with this idempotency key was already sent."""

    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(f"outbound message already delivered: {idempotency_key!r}")


# --- Tool / agent layer -------------------------------------------------


class ToolError(JobPilotError):
    """Base class for agent tool failures."""


class UnknownToolError(ToolError):
    """The agent requested a tool name that is not in the registry."""


class ToolArgumentError(ToolError):
    """A tool call's arguments failed schema validation."""


# --- Integrations (external boundaries) ---------------------------------


class IntegrationError(JobPilotError):
    """Base class for failures at an external system boundary."""


class LLMProviderError(IntegrationError):
    """The configured LLM provider returned an error or malformed output."""


class ObjectStorageError(IntegrationError):
    """The object storage backend failed to read or write a blob."""


class QueueError(IntegrationError):
    """The queue backend failed to enqueue, receive, or delete a message."""


class RepositoryError(IntegrationError):
    """A database repository operation failed."""


class RecordNotFoundError(RepositoryError):
    """A repository lookup found no matching row."""
