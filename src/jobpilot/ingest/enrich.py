"""LLM enrichment: turn a `RawPosting` into a validated `JobRecord`.

The LLM call itself returns JSON matching the contract described in
`ENRICHMENT_SYSTEM_PROMPT`; this module is responsible for parsing
that JSON, validating it hard against the taxonomy (a category or
band outside the enum is a bug in the model output, not a soft
warning), and raising `EnrichmentSchemaError` with enough detail to
debug a bad prompt response.
"""

from __future__ import annotations

import json

from jobpilot.errors import EnrichmentSchemaError
from jobpilot.ingest.prompts import ENRICHMENT_SYSTEM_PROMPT, IDEAL_CANDIDATE_PROMPT
from jobpilot.integrations.llm import LLMClient
from jobpilot.models import (
    CompensationRange,
    EmploymentType,
    FraudSignal,
    JobRecord,
    LocationTier,
    RawPosting,
    RoleCategory,
    SeniorityBand,
    seniority_band_for_years,
)
from jobpilot.utils.text import clean_posting_text


def enrich_posting(llm: LLMClient, posting: RawPosting) -> JobRecord:
    """Run enrichment for one posting and return a validated `JobRecord`."""

    cleaned_description = clean_posting_text(posting.description)

    user_message = (
        f"Title: {posting.title}\nCompany: {posting.company}\n"
        f"Description:\n{cleaned_description}\n\n{IDEAL_CANDIDATE_PROMPT}"
    )
    response = llm.complete(
        system_prompt=ENRICHMENT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        temperature=0.1,
    )

    content = response.get("content")
    if not content:
        raise EnrichmentSchemaError("enrichment call returned no content")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise EnrichmentSchemaError(f"enrichment output was not valid JSON: {exc}") from exc

    return _build_job_record(posting, payload, cleaned_description)


def _build_job_record(posting: RawPosting, payload: dict, cleaned_description: str) -> JobRecord:
    required_keys = {
        "role_category",
        "seniority_band",
        "min_years_experience",
        "skills",
        "location_tier",
        "employment_type",
        "fraud_signal",
        "candidate_profile_text",
    }
    missing = required_keys - payload.keys()
    if missing:
        raise EnrichmentSchemaError(f"enrichment output missing keys: {sorted(missing)}")

    try:
        role_category = RoleCategory(payload["role_category"])
    except ValueError as exc:
        raise EnrichmentSchemaError(
            f"enrichment returned role_category outside the taxonomy: {payload['role_category']!r}"
        ) from exc

    try:
        location_tier = LocationTier(payload["location_tier"])
    except ValueError as exc:
        raise EnrichmentSchemaError(
            f"enrichment returned location_tier outside the taxonomy: {payload['location_tier']!r}"
        ) from exc

    try:
        employment_type = EmploymentType(payload["employment_type"])
    except ValueError as exc:
        raise EnrichmentSchemaError(
            f"enrichment returned employment_type outside the taxonomy: {payload['employment_type']!r}"
        ) from exc

    try:
        fraud_signal = FraudSignal(payload["fraud_signal"])
    except ValueError as exc:
        raise EnrichmentSchemaError(
            f"enrichment returned fraud_signal outside the taxonomy: {payload['fraud_signal']!r}"
        ) from exc

    min_years = float(payload["min_years_experience"])
    try:
        seniority_band = SeniorityBand(payload["seniority_band"])
    except ValueError as exc:
        raise EnrichmentSchemaError(
            f"enrichment returned seniority_band outside the taxonomy: {payload['seniority_band']!r}"
        ) from exc

    # INTERN is only valid at exactly 0 years and is not derivable from
    # years alone (0 years also covers ENTRY) — an internship posting
    # must say so explicitly, so a claimed INTERN band is only trusted
    # when the years are consistent with it; otherwise fall through to
    # the deterministic years-based correction below.
    if seniority_band == SeniorityBand.INTERN and min_years == 0:
        pass
    else:
        expected_band = seniority_band_for_years(min_years)
        if seniority_band != expected_band:
            # The model computed years and band inconsistently; trust
            # the years (a number) over the band (a label) and correct
            # it, rather than failing enrichment outright for a
            # mismatch we can deterministically repair.
            seniority_band = expected_band

    compensation = None
    if payload.get("compensation"):
        try:
            compensation = CompensationRange.model_validate(payload["compensation"])
        except Exception as exc:  # pydantic ValidationError
            raise EnrichmentSchemaError(f"enrichment returned invalid compensation: {exc}") from exc

    candidate_profile_text = payload["candidate_profile_text"].strip()
    if not candidate_profile_text:
        raise EnrichmentSchemaError("enrichment returned an empty candidate_profile_text")

    return JobRecord(
        source_platform=posting.source_platform,
        source_listing_id=posting.source_listing_id,
        content_hash=posting.content_hash,
        title=posting.title,
        company=posting.company,
        description=cleaned_description,
        apply_url=posting.apply_url,
        role_category=role_category,
        seniority_band=seniority_band,
        min_years_experience=min_years,
        skills=list(payload["skills"]),
        location_text=payload.get("location_text") or posting.location_text,
        location_tier=location_tier,
        employment_type=employment_type,
        compensation=compensation,
        fraud_signal=fraud_signal,
        fraud_signal_reason=payload.get("fraud_signal_reason"),
        candidate_profile_text=candidate_profile_text,
        posted_at=posting.posted_at,
    )
