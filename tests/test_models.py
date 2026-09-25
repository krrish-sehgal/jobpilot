from __future__ import annotations

import pytest
from pydantic import ValidationError

from jobpilot.models import CompensationRange, SeniorityBand, seniority_band_for_years
from tests.conftest import make_job_record


@pytest.mark.parametrize(
    "years,expected",
    [
        (0, SeniorityBand.ENTRY),
        (1, SeniorityBand.ENTRY),
        (2, SeniorityBand.MID),
        (4.5, SeniorityBand.MID),
        (5, SeniorityBand.SENIOR),
        (9, SeniorityBand.SENIOR),
        (10, SeniorityBand.LEADERSHIP),
        (25, SeniorityBand.LEADERSHIP),
    ],
)
def test_seniority_band_for_years(years, expected):
    assert seniority_band_for_years(years) == expected


def test_seniority_band_for_years_rejects_negative():
    with pytest.raises(ValueError):
        seniority_band_for_years(-1)


def test_job_record_rejects_inconsistent_seniority_and_years():
    with pytest.raises(ValidationError):
        make_job_record(seniority_band=SeniorityBand.LEADERSHIP, min_years_experience=1)


def test_job_record_allows_intern_at_zero_years():
    job = make_job_record(seniority_band=SeniorityBand.INTERN, min_years_experience=0)
    assert job.seniority_band == SeniorityBand.INTERN


def test_job_record_rejects_intern_with_nonzero_years():
    with pytest.raises(ValidationError):
        make_job_record(seniority_band=SeniorityBand.INTERN, min_years_experience=1)


def test_job_record_dedupes_and_lowercases_skills():
    job = make_job_record(skills=["Python", "python", "  Go  ", "GO"])
    assert job.skills == ["python", "go"]


def test_compensation_range_rejects_min_greater_than_max():
    with pytest.raises(ValidationError):
        CompensationRange(currency="USD", min_amount=200000, max_amount=100000)


def test_compensation_range_allows_open_ended_bounds():
    comp = CompensationRange(currency="USD", min_amount=100000, max_amount=None)
    assert comp.max_amount is None
