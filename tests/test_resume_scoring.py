from __future__ import annotations

from datetime import date

import pytest

from jobpilot.models import SeniorityBand
from jobpilot.resume.keywords import JobKeywords, compute_coverage
from jobpilot.resume.models import ExperienceEntry, ResumeSections
from jobpilot.resume.scoring import (
    ScoreWeights,
    candidate_band,
    estimate_years_experience,
    parse_year_month,
    recency_of_relevant_experience,
    score_match,
    seniority_fit,
)
from tests.resume_fixtures import sample_sections

TODAY = date(2026, 6, 15)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Jun 2021", (2021, 6)),
        ("September 2019", (2019, 9)),
        ("06/2021", (2021, 6)),
        ("2021-03", (2021, 3)),
        ("2020", (2020, 1)),
        ("Present", (2026, 6)),
        ("sometime", None),
        (None, None),
    ],
)
def test_parse_year_month(text, expected):
    assert parse_year_month(text, today=TODAY) == expected


def test_years_of_experience_counts_overlaps_once():
    sections = ResumeSections(
        experience=[
            ExperienceEntry(company="A", title="Dev", start="Jan 2020", end="Dec 2021"),
            ExperienceEntry(company="B", title="Dev", start="Jan 2021", end="Dec 2022"),
        ]
    )
    # Jan 2020 .. Dec 2022 contiguous: 35 months
    assert estimate_years_experience(sections, today=TODAY) == pytest.approx(35 / 12)


def test_candidate_band_from_sample_resume():
    # Jun 2019 .. Jun 2026 is ~7 years: senior
    assert candidate_band(sample_sections(), today=TODAY) == SeniorityBand.SENIOR
    assert candidate_band(ResumeSections(), today=TODAY) == SeniorityBand.ENTRY


def test_seniority_fit_is_asymmetric_and_neutral_when_unknown():
    s, m = SeniorityBand.SENIOR, SeniorityBand.MID
    assert seniority_fit(s, s) == 1.0
    assert seniority_fit(s, m) == 0.75  # overqualified by one level
    assert seniority_fit(m, s) == 0.6  # one level short
    assert seniority_fit(SeniorityBand.ENTRY, SeniorityBand.SENIOR) == pytest.approx(0.2)
    assert seniority_fit(SeniorityBand.ENTRY, SeniorityBand.LEADERSHIP) == 0.0
    assert seniority_fit(s, None) == 0.5


def test_recency_full_for_current_role_and_decays_for_old_work():
    sections = sample_sections()
    assert recency_of_relevant_experience(sections, ["redis"], today=TODAY) == 1.0
    # Flask only appears in the role that ended Dec 2021: 54 months ago
    expected = 0.5 ** ((54 - 12) / 24)
    assert recency_of_relevant_experience(sections, ["flask"], today=TODAY) == pytest.approx(
        expected
    )


def test_recency_falls_back_to_projects_then_zero():
    sections = sample_sections()
    # Elasticsearch appears only in an (undated) project
    assert recency_of_relevant_experience(sections, ["elasticsearch"], today=TODAY) == 0.5
    sections.experience = []
    assert recency_of_relevant_experience(sections, ["kubernetes"], today=TODAY) == 0.0
    assert recency_of_relevant_experience(sections, [], today=TODAY) == 0.5


def test_score_is_weighted_and_bounded():
    sections = sample_sections()
    keywords = JobKeywords(required=("python", "kubernetes"), preferred=("redis",))
    entries = compute_coverage(keywords, sections)
    breakdown = score_match(sections, entries, SeniorityBand.SENIOR, today=TODAY)
    assert breakdown.required == 0.5 and breakdown.preferred == 1.0
    assert breakdown.seniority == 1.0 and breakdown.recency == 1.0
    assert breakdown.total == pytest.approx(100 * (0.55 * 0.5 + 0.15 + 0.15 + 0.15), abs=0.05)
    assert 0 <= breakdown.total <= 100


def test_missing_components_are_dropped_not_awarded():
    sections = sample_sections()
    entries = compute_coverage(JobKeywords(required=("python",), preferred=()), sections)
    breakdown = score_match(sections, entries, SeniorityBand.SENIOR, today=TODAY)
    assert breakdown.preferred is None
    assert breakdown.total == 100.0  # python covered, senior fit, current role


def test_after_flag_reads_covered_after():
    sections = sample_sections()
    entries = compute_coverage(
        JobKeywords(required=("python", "kubernetes"), preferred=()), sections
    )
    before = score_match(sections, entries, SeniorityBand.SENIOR, today=TODAY)
    entries[1].covered_after = True
    after = score_match(sections, entries, SeniorityBand.SENIOR, after=True, today=TODAY)
    assert after.total > before.total
    assert after.required == 1.0


def test_default_weights_sum_to_one():
    w = ScoreWeights()
    assert w.required + w.preferred + w.seniority + w.recency == pytest.approx(1.0)
