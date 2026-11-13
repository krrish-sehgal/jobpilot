from __future__ import annotations

import json

import pytest

from jobpilot.errors import LLMProviderError, ResumeParseError
from jobpilot.integrations.llm import FakeLLMClient
from jobpilot.resume.keywords import (
    JobKeywords,
    compute_coverage,
    contains_term,
    coverage_fraction,
    extract_job_keywords,
    normalize_term,
    resume_text,
)
from jobpilot.resume.models import KeywordImportance
from tests.resume_fixtures import sample_sections


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("JS", "javascript"),
        (" K8s ", "kubernetes"),
        ("Postgres", "postgresql"),
        ("Golang", "go"),
        ("NodeJS", "node.js"),
        ("Python.", "python"),
        ("C++", "c++"),
        (".NET", ".net"),
        ("Machine   Learning", "machine learning"),
        ("(React.js)", "react"),
    ],
)
def test_normalize_term(raw, expected):
    assert normalize_term(raw) == expected


def test_contains_term_understands_aliases_in_both_directions():
    assert contains_term("Deployed on k8s clusters", "Kubernetes")
    assert contains_term("Deployed on Kubernetes", "k8s")
    assert contains_term("Wrote PostgreSQL migrations", "postgres")


def test_contains_term_respects_word_boundaries():
    assert not contains_term("Built a JavaScript frontend", "java")
    assert not contains_term("Used Node.js for tooling", "no")
    assert contains_term("Primary language: Java.", "java")
    assert contains_term("Services in C++ and Go", "c++")
    assert not contains_term("Wrote C code", "c++")


def test_resume_text_excludes_contact_and_can_exclude_skills():
    sections = sample_sections()
    sections.skills.append("Haskell")
    full = resume_text(sections)
    assert "priya@example.com" not in full and "Bengaluru" not in full
    assert contains_term(full, "Haskell")
    evidence_only = resume_text(sections, include_skills=False)
    assert contains_term(evidence_only, "Flask")  # demonstrated in a bullet
    assert not contains_term(evidence_only, "Haskell")  # only listed, never used


def test_coverage_marks_found_and_missing_terms():
    keywords = JobKeywords(
        required=("python", "postgres", "kubernetes"), preferred=("redis", "terraform")
    )
    entries = compute_coverage(keywords, sample_sections())
    found = {e.term: e.found_in_resume for e in entries}
    assert found == {
        "python": True,
        "postgres": True,  # resume says PostgreSQL
        "kubernetes": False,
        "redis": True,  # appears in a bullet, not the skills list
        "terraform": False,
    }
    assert all(e.covered_after == e.found_in_resume for e in entries)
    assert coverage_fraction(entries, KeywordImportance.REQUIRED) == pytest.approx(2 / 3)
    assert coverage_fraction(entries, KeywordImportance.PREFERRED) == 0.5
    assert coverage_fraction([], KeywordImportance.REQUIRED) is None


def _llm(payload) -> FakeLLMClient:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return FakeLLMClient(
        responder=lambda s, m: {"content": content, "tool_calls": [], "finish_reason": "stop"}
    )


def test_extraction_merges_structured_skills_and_llm_terms():
    llm = _llm(
        {
            "job_title": "Backend Engineer",
            "company": "Globex",
            "required": ["Python", "K8s", "python"],
            "preferred": ["Terraform", "kubernetes", "Redis"],
        }
    )
    result = extract_job_keywords(
        llm, title="Backend Engineer", description="...", skills=["Go", "python"]
    )
    assert result.required == ("go", "python", "kubernetes")
    # a term that is required is never also listed as preferred
    assert result.preferred == ("terraform", "redis")
    assert (result.job_title, result.company) == ("Backend Engineer", "Globex")


def test_extraction_degrades_to_structured_skills_when_llm_fails():
    llm = _llm("this is not json")
    result = extract_job_keywords(llm, title="t", description="d", skills=["python", "go"])
    assert result.required == ("python", "go") and result.preferred == ()


def test_extraction_without_any_signal_raises():
    def boom(system_prompt, messages):
        raise LLMProviderError("down")

    with pytest.raises(ResumeParseError):
        extract_job_keywords(FakeLLMClient(responder=boom), title="t", description="d")
    with pytest.raises(ResumeParseError):
        extract_job_keywords(_llm({"required": [], "preferred": []}), title="t", description="d")
