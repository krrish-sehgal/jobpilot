from __future__ import annotations

import json

import pytest

from jobpilot.errors import EnrichmentSchemaError
from jobpilot.ingest.enrich import enrich_posting
from jobpilot.integrations.llm import FakeLLMClient
from jobpilot.models import RawPosting, RoleCategory, SeniorityBand
from jobpilot.utils.hashing import content_hash

_VALID_PAYLOAD = {
    "role_category": "software_engineering",
    "seniority_band": "senior",
    "min_years_experience": 5,
    "skills": ["python", "go"],
    "location_text": "Remote",
    "location_tier": "remote",
    "employment_type": "full_time",
    "compensation": {
        "currency": "USD",
        "min_amount": 150000,
        "max_amount": 180000,
        "period": "year",
    },
    "fraud_signal": "none",
    "fraud_signal_reason": None,
    "candidate_profile_text": "Has 5+ years building backend systems in Python and Go.",
}


def make_posting() -> RawPosting:
    title, company, description = "Senior Backend Engineer", "Acme", "Build the payments API. " * 10
    return RawPosting(
        source_platform="talentflow",
        source_listing_id="abc",
        title=title,
        company=company,
        description=description,
        apply_url="https://apply.example.com/1",
        content_hash=content_hash(title, company, description),
    )


def responder_returning(payload: dict):
    def _respond(system_prompt, messages):
        return {"content": json.dumps(payload), "tool_calls": [], "finish_reason": "stop"}

    return _respond


def test_enrich_posting_produces_valid_job_record():
    llm = FakeLLMClient(responder=responder_returning(_VALID_PAYLOAD))
    job = enrich_posting(llm, make_posting())
    assert job.role_category == RoleCategory.SOFTWARE_ENGINEERING
    assert job.seniority_band == SeniorityBand.SENIOR
    assert job.compensation.min_amount == 150000
    assert "python" in job.skills


def test_enrich_posting_rejects_invalid_role_category():
    bad_payload = dict(_VALID_PAYLOAD, role_category="astrology")
    llm = FakeLLMClient(responder=responder_returning(bad_payload))
    with pytest.raises(EnrichmentSchemaError):
        enrich_posting(llm, make_posting())


def test_enrich_posting_corrects_inconsistent_seniority_band():
    # min_years_experience=1 implies "entry", but the model said "senior" —
    # enrich_posting should deterministically correct this from the years.
    bad_payload = dict(_VALID_PAYLOAD, min_years_experience=1, seniority_band="senior")
    llm = FakeLLMClient(responder=responder_returning(bad_payload))
    job = enrich_posting(llm, make_posting())
    assert job.seniority_band == SeniorityBand.ENTRY


def test_enrich_posting_rejects_non_json_content():
    def _respond(system_prompt, messages):
        return {"content": "not json at all", "tool_calls": [], "finish_reason": "stop"}

    llm = FakeLLMClient(responder=_respond)
    with pytest.raises(EnrichmentSchemaError):
        enrich_posting(llm, make_posting())


def test_enrich_posting_rejects_missing_required_keys():
    incomplete = {"role_category": "software_engineering"}
    llm = FakeLLMClient(responder=responder_returning(incomplete))
    with pytest.raises(EnrichmentSchemaError):
        enrich_posting(llm, make_posting())


def test_enrich_posting_accepts_intern_at_zero_years():
    payload = dict(_VALID_PAYLOAD, seniority_band="intern", min_years_experience=0)
    llm = FakeLLMClient(responder=responder_returning(payload))
    job = enrich_posting(llm, make_posting())
    assert job.seniority_band == SeniorityBand.INTERN


def test_enrich_posting_rejects_empty_candidate_profile_text():
    bad_payload = dict(_VALID_PAYLOAD, candidate_profile_text="   ")
    llm = FakeLLMClient(responder=responder_returning(bad_payload))
    with pytest.raises(EnrichmentSchemaError):
        enrich_posting(llm, make_posting())
