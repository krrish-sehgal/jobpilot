"""The fabrication guard: what it must reject, and what it must let through."""

from __future__ import annotations

import pytest

from jobpilot.resume.guard import FabricationGuard, extract_numbers
from jobpilot.resume.models import ResumeSections, Suggestion, SuggestionKind, SuggestionSection
from tests.resume_fixtures import sample_sections

JOB_TERMS = ["python", "kubernetes", "terraform", "redis"]


def bullet_id(sections: ResumeSections, startswith: str) -> str:
    for entry in [*sections.experience, *sections.projects]:
        for bullet in entry.bullets:
            if bullet.text.startswith(startswith):
                return bullet.id
    raise AssertionError(startswith)


def rewrite(sections: ResumeSections, startswith: str, proposed: str, **kw) -> Suggestion:
    return Suggestion(
        kind=SuggestionKind.REWRITE_BULLET,
        section=SuggestionSection.EXPERIENCE,
        target_id=bullet_id(sections, startswith),
        proposed=proposed,
        **kw,
    )


def add_skill(skill: str) -> Suggestion:
    return Suggestion(
        kind=SuggestionKind.ADD_SKILL, section=SuggestionSection.SKILLS, proposed=skill
    )


@pytest.fixture
def sections() -> ResumeSections:
    return sample_sections()


@pytest.fixture
def guard(sections) -> FabricationGuard:
    return FabricationGuard(sections, JOB_TERMS)


# --- accepted -----------------------------------------------------------


def test_honest_rewrite_reusing_original_facts_passes(guard, sections):
    s = rewrite(
        sections,
        "Reduced API latency",
        "Cut API latency by 35% by introducing Redis caching",
        keywords_added=["redis"],
    )
    verdict = guard.check(s)
    assert verdict.ok, verdict.violations


def test_numbers_are_compared_regardless_of_formatting(guard, sections):
    s = rewrite(
        sections,
        "Built a payment",
        "Built a Python and PostgreSQL reconciliation service handling 2,000,000 daily"
        " transactions",
    )
    # "2,000,000" is not "2" from "2 million": different number, rejected
    assert not guard.check(s).ok
    assert extract_numbers("1,000 and 1000.") == {"1000"}


def test_summary_rewrite_and_reorder_pass(guard, sections):
    summary = Suggestion(
        kind=SuggestionKind.REWRITE_SUMMARY,
        section=SuggestionSection.SUMMARY,
        proposed="Backend engineer experienced in building Python services on AWS.",
    )
    reorder = Suggestion(
        kind=SuggestionKind.REORDER_SECTION,
        section=SuggestionSection.SKILLS,
        target_id="skills",
        proposed="aws, Python, Docker, Flask, PostgreSQL",
    )
    assert guard.check(summary).ok
    assert guard.check(reorder).ok


@pytest.mark.parametrize("skill", ["Redis", "Jenkins", "redis"])
def test_add_skill_is_allowed_when_demonstrated_elsewhere(guard, skill):
    verdict = guard.check(add_skill(skill))
    assert verdict.ok, verdict.violations


# --- rejected -----------------------------------------------------------


@pytest.mark.parametrize(
    ("startswith", "proposed", "expected"),
    [
        ("Reduced API latency", "Reduced API latency by 50% by adding Redis caching", "numbers"),
        ("Reduced API latency", "Reduced API latency by 35% in 2023 with Redis caching", "numbers"),
        ("Mentored 3 junior engineers", "Mentored 12 junior engineers", "numbers"),
        (
            "Mentored 3 junior engineers",
            "Mentored 3 junior engineers and doubled throughput",
            "quantitative",
        ),
        ("Built a payment", "Built a reconciliation service at Stripe using Python", "names"),
        ("Developed REST APIs", "Developed REST APIs for Google teams", "names"),
        (
            "Mentored 3 junior engineers",
            "Mentored 3 junior engineers as principal engineer",
            "title",
        ),
        ("Mentored 3 junior engineers", "Mentored 3 junior engineers as a director", "title"),
        (
            "Wrote CI pipelines",
            "Wrote CI pipelines in Jenkins and ran kubernetes clusters",
            "never",
        ),
        ("Wrote CI pipelines", "Wrote CI pipelines in Jenkins using Terraform", "names"),
        ("Mentored 3 junior engineers", "Mentored 3 junior engineers", "change"),
    ],
)
def test_rewrites_that_invent_facts_are_rejected(guard, sections, startswith, proposed, expected):
    verdict = guard.check(rewrite(sections, startswith, proposed))
    assert not verdict.ok
    assert any(expected in v for v in verdict.violations), verdict.violations


def test_rewrite_claiming_unsupported_keywords_is_rejected(guard, sections):
    s = rewrite(
        sections,
        "Developed REST APIs",
        "Developed REST APIs with Flask used by 12 internal teams",
        keywords_added=["terraform"],
    )
    assert not guard.check(s).ok


@pytest.mark.parametrize("skill", ["Kubernetes", "Terraform"])
def test_add_skill_is_rejected_when_not_in_resume(guard, skill):
    assert "not demonstrated" in guard.check(add_skill(skill)).violations[0]


def test_add_skill_rejects_duplicates_and_sentences(guard):
    assert not guard.check(add_skill("python")).ok
    assert not guard.check(add_skill("Strong Redis experience. Also Jenkins")).ok


def test_skill_only_listed_is_not_evidence(sections):
    sections.skills.append("Haskell")  # listed, never used in any bullet
    guard = FabricationGuard(sections, JOB_TERMS)
    assert not guard.check(add_skill("Haskell")).ok  # already listed anyway
    sections.skills.remove("AWS")  # AWS stays in the summary, so it is demonstrated
    assert FabricationGuard(sections).check(add_skill("AWS")).ok


def test_structural_violations(guard, sections):
    missing_bullet = Suggestion(
        kind=SuggestionKind.REWRITE_BULLET,
        section=SuggestionSection.EXPERIENCE,
        target_id="not-a-real-id",
        proposed="Anything",
    )
    bad_reorder = Suggestion(
        kind=SuggestionKind.REORDER_SECTION,
        section=SuggestionSection.SKILLS,
        target_id="skills",
        proposed="Python, Flask, Kubernetes",
    )
    reorder_experience = Suggestion(
        kind=SuggestionKind.REORDER_SECTION,
        section=SuggestionSection.EXPERIENCE,
        target_id="experience",
        proposed="Bright Labs, Acme Payments",
    )
    assert not guard.check(missing_bullet).ok
    assert not guard.check(bad_reorder).ok
    assert not guard.check(reorder_experience).ok

    sections.summary = None
    no_summary = Suggestion(
        kind=SuggestionKind.REWRITE_SUMMARY, section=SuggestionSection.SUMMARY, proposed="New."
    )
    assert not FabricationGuard(sections).check(no_summary).ok


def test_filter_splits_kept_and_rejected_with_reasons(guard, sections):
    good = add_skill("Redis")
    bad = add_skill("Kubernetes")
    kept, rejected = guard.filter([good, bad])
    assert kept == [good]
    assert rejected[0][0] is bad and rejected[0][1].violations
