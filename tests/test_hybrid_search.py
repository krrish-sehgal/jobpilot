from __future__ import annotations

from jobpilot.integrations.llm import FakeLLMClient
from jobpilot.models import LocationTier, RoleCategory, SearchFilters, SeniorityBand
from jobpilot.search.hybrid import apply_filters, hybrid_search
from tests.conftest import make_job_record


def test_apply_filters_by_role_category():
    eng_job = make_job_record(role_category=RoleCategory.SOFTWARE_ENGINEERING)
    sales_job = make_job_record(role_category=RoleCategory.SALES_AND_BUSINESS_DEV)
    filters = SearchFilters(role_categories=[RoleCategory.SOFTWARE_ENGINEERING])
    result = apply_filters([eng_job, sales_job], filters)
    assert result == [eng_job]


def test_apply_filters_excludes_fraud_by_default():
    from jobpilot.models import FraudSignal

    scammy = make_job_record(fraud_signal=FraudSignal.LIKELY_SCAM)
    clean = make_job_record(fraud_signal=FraudSignal.NONE)
    result = apply_filters([scammy, clean], SearchFilters())
    assert result == [clean]


def test_apply_filters_by_location_tier():
    remote = make_job_record(location_tier=LocationTier.REMOTE)
    onsite = make_job_record(location_tier=LocationTier.ONSITE)
    filters = SearchFilters(location_tiers=[LocationTier.REMOTE])
    result = apply_filters([remote, onsite], filters)
    assert result == [remote]


def test_hybrid_search_returns_identical_text_as_top_match():
    llm = FakeLLMClient()
    matching = make_job_record(
        candidate_profile_text="loves rust and distributed systems at a small startup"
    )
    unrelated = make_job_record(
        candidate_profile_text="experienced sales leader closing enterprise deals"
    )
    results = hybrid_search(
        llm,
        query_text="loves rust and distributed systems at a small startup",
        candidate_jobs=[unrelated, matching],
    )
    assert results
    assert results[0].job.id == matching.id


def test_hybrid_search_empty_after_filters_returns_empty():
    llm = FakeLLMClient()
    job = make_job_record(seniority_band=SeniorityBand.ENTRY, min_years_experience=0)
    filters = SearchFilters(seniority_bands=[SeniorityBand.LEADERSHIP])
    results = hybrid_search(llm, query_text="anything", candidate_jobs=[job], filters=filters)
    assert results == []


def test_hybrid_search_respects_limit():
    llm = FakeLLMClient()
    jobs = [make_job_record(title=f"Role {i}") for i in range(10)]
    results = hybrid_search(llm, query_text="python backend", candidate_jobs=jobs, limit=3)
    assert len(results) == 3
