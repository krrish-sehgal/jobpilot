"""
Enrichment: turning a messy, human-written job posting into a strict
structured record.

Job postings are free text written by whoever happened to write them —
inconsistent formatting, missing fields, marketing fluff, sometimes
outright scams. This step sends the raw text to an LLM along with a
fixed schema and a small invented taxonomy, and gets back something a
database and a search index can actually work with.

The taxonomy below is invented for this demo project. It is not meant
to resemble any particular real-world classification system — it's
just small enough to be readable as an example.
"""

from __future__ import annotations

from dataclasses import dataclass

from jobpilot.agent.prompts import ENRICH_JOB_PROMPT
from jobpilot.ingest.scrapers.base import RawPosting

# --- Invented taxonomy: about 6 role categories ---
ROLE_CATEGORIES = [
    "engineering",
    "data_and_analytics",
    "design",
    "sales_and_marketing",
    "operations",
    "customer_support",
]

# --- Invented taxonomy: 4 seniority bands ---
SENIORITY_BANDS = [
    "entry",
    "junior",
    "mid",
    "senior",
]


@dataclass
class EnrichedJob:
    """The strict record an LLM would be asked to produce from one
    RawPosting, per ENRICH_JOB_PROMPT."""

    source_posting_id: str
    role_category: str
    seniority_band: str
    skills: list[str]
    location: str | None
    pay_range: str | None
    scam_risk: bool
    scam_risk_reason: str | None


def enrich_posting(posting: RawPosting) -> EnrichedJob:
    """Send a raw posting to an LLM with ENRICH_JOB_PROMPT and parse the
    response into an EnrichedJob, validating that role_category and
    seniority_band fall inside the taxonomy above.

    This demo never calls a model. It exists to show where that call
    happens in the pipeline (see docs/architecture.md) and what shape
    the output takes.
    """
    raise NotImplementedError("demo only: no real LLM call is made")


def validate_taxonomy(role_category: str, seniority_band: str) -> None:
    """Raise if a proposed classification falls outside the small
    invented taxonomy this project uses. A real system would reject or
    flag-for-review any record that fails this check rather than
    silently accepting an out-of-taxonomy value.
    """
    if role_category not in ROLE_CATEGORIES:
        raise ValueError(f"unknown role_category: {role_category!r}")
    if seniority_band not in SENIORITY_BANDS:
        raise ValueError(f"unknown seniority_band: {seniority_band!r}")


__all__ = [
    "ROLE_CATEGORIES",
    "SENIORITY_BANDS",
    "EnrichedJob",
    "enrich_posting",
    "validate_taxonomy",
    "ENRICH_JOB_PROMPT",
]
