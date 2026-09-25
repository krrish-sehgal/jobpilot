from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jobpilot.errors import RankingWeightError
from jobpilot.models import LocationTier, SeniorityBand
from jobpilot.search.ranking import (
    RankingWeights,
    completeness_score,
    location_fit_score,
    recency_score,
    score_job,
    seniority_fit_score,
)
from tests.conftest import make_job_record


def test_ranking_weights_must_sum_to_one():
    with pytest.raises(RankingWeightError):
        RankingWeights(semantic=0.5, recency=0.5, seniority_fit=0.5, location_fit=0, completeness=0)


def test_recency_score_decays_with_age():
    now = datetime.now(UTC)
    fresh = recency_score(now, now=now)
    two_weeks_old = recency_score(now - timedelta(days=14), now=now)
    assert fresh == pytest.approx(1.0)
    assert two_weeks_old == pytest.approx(0.5, abs=1e-6)
    assert fresh > two_weeks_old


def test_recency_score_missing_date_is_neutral():
    assert recency_score(None) == 0.5


def test_seniority_fit_exact_match_is_one():
    assert seniority_fit_score(SeniorityBand.SENIOR, SeniorityBand.SENIOR) == 1.0


def test_seniority_fit_decays_with_distance():
    close = seniority_fit_score(SeniorityBand.SENIOR, SeniorityBand.MID)
    far = seniority_fit_score(SeniorityBand.LEADERSHIP, SeniorityBand.INTERN)
    assert 0 < close < 1
    assert far == 0.0
    assert close > far


def test_seniority_fit_unknown_candidate_is_neutral():
    assert seniority_fit_score(SeniorityBand.SENIOR, None) == 0.5


def test_location_fit_scores():
    assert location_fit_score(LocationTier.REMOTE, [LocationTier.REMOTE]) == 1.0
    assert location_fit_score(LocationTier.ONSITE, [LocationTier.REMOTE]) == 0.0
    assert location_fit_score(LocationTier.REMOTE, None) == 0.5
    assert location_fit_score(LocationTier.UNKNOWN, [LocationTier.REMOTE]) == 0.3


def test_completeness_score_rewards_filled_fields():
    thin = make_job_record(skills=[], location_tier=LocationTier.UNKNOWN, posted_at=None)
    thin = thin.model_copy(update={"description": "short"})
    rich = make_job_record()
    assert completeness_score(rich) > completeness_score(thin)


def test_score_job_combined_score_in_bounds():
    job = make_job_record()
    scored = score_job(job, semantic_similarity=0.8)
    assert 0.0 <= scored.combined_score <= 1.0


def test_score_job_rejects_out_of_range_similarity():
    job = make_job_record()
    with pytest.raises(ValueError):
        score_job(job, semantic_similarity=1.5)


def test_higher_semantic_similarity_yields_higher_combined_score():
    job = make_job_record()
    low = score_job(job, semantic_similarity=0.1)
    high = score_job(job, semantic_similarity=0.9)
    assert high.combined_score > low.combined_score
