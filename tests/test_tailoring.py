"""Tailoring pipeline, decision application, and rendering."""

from __future__ import annotations

import json
import zipfile
from datetime import date
from io import BytesIO

import pytest

from jobpilot.integrations.llm import FakeLLMClient
from jobpilot.models import SeniorityBand
from jobpilot.resume.apply import apply_decisions, apply_suggestions
from jobpilot.resume.keywords import JobKeywords
from jobpilot.resume.models import (
    Decision,
    Suggestion,
    SuggestionKind,
    SuggestionSection,
)
from jobpilot.resume.prompts import TAILOR_SYSTEM_PROMPT
from jobpilot.resume.render import (
    DocumentFormat,
    StubDocumentRenderer,
    render_html,
    render_text,
)
from jobpilot.resume.tailor import generate_suggestions, rescore, tailor_resume
from tests.resume_fixtures import sample_sections
from tests.test_fabrication_guard import bullet_id

TODAY = date(2026, 6, 15)
KEYWORDS = JobKeywords(required=("python", "jenkins", "kubernetes"), preferred=("redis",))


def _llm(suggestions: list[dict]) -> FakeLLMClient:
    def responder(system_prompt, messages):
        assert system_prompt == TAILOR_SYSTEM_PROMPT
        payload = json.loads(messages[0]["content"])
        assert "kubernetes" in payload["job"]["missing"]
        return {
            "content": json.dumps({"suggestions": suggestions}),
            "tool_calls": [],
            "finish_reason": "stop",
        }

    return FakeLLMClient(responder=responder)


def _run(suggestions: list[dict]):
    return tailor_resume(
        _llm(suggestions),
        sample_sections(),
        KEYWORDS,
        job_title="Backend Engineer",
        company="Globex",
        job_band=SeniorityBand.SENIOR,
        today=TODAY,
    )


GOOD_SKILL = {
    "kind": "add_skill",
    "section": "skills",
    "target_id": None,
    "proposed": "Jenkins",
    "reason": "Jenkins is required and your CI work shows it.",
    "keywords_added": ["jenkins"],
}
INVENTED_SKILL = {**GOOD_SKILL, "proposed": "Kubernetes", "keywords_added": ["kubernetes"]}


def test_guarded_pipeline_keeps_honest_suggestions_and_scores_the_gain():
    outcome = _run([GOOD_SKILL, INVENTED_SKILL])
    assert [s.proposed for s in outcome.suggestions] == ["Jenkins"]
    assert [s.proposed for s, _ in outcome.rejected] == ["Kubernetes"]
    assert outcome.score_after > outcome.score_before
    by_term = {e.term: e for e in outcome.keywords}
    assert by_term["jenkins"].found_in_resume and by_term["jenkins"].covered_after
    assert not by_term["kubernetes"].found_in_resume and not by_term["kubernetes"].covered_after


def test_no_surviving_suggestions_means_no_score_change():
    outcome = _run([INVENTED_SKILL])
    assert outcome.suggestions == []
    assert outcome.score_after == outcome.score_before


def test_generation_fills_original_from_the_resume_not_the_model():
    sections = sample_sections()
    target = bullet_id(sections, "Mentored")
    raw = {
        "kind": "rewrite_bullet",
        "section": "experience",
        "target_id": target,
        "proposed": "Coached 3 junior engineers",
        "original": "something the model invented",
    }
    entries = []
    suggestions = generate_suggestions(
        _llm_ignoring_missing([raw]), sections, KEYWORDS, entries, job_title="t", company=None
    )
    assert suggestions[0].original == "Mentored 3 junior engineers"


def _llm_ignoring_missing(items: list[dict]) -> FakeLLMClient:
    return FakeLLMClient(
        responder=lambda s, m: {
            "content": json.dumps({"suggestions": items}),
            "tool_calls": [],
            "finish_reason": "stop",
        }
    )


def test_malformed_and_duplicate_suggestions_are_skipped():
    items = [{"kind": "nope"}, "text", GOOD_SKILL, GOOD_SKILL]
    suggestions = generate_suggestions(
        _llm_ignoring_missing(items), sample_sections(), KEYWORDS, [], job_title="t", company=None
    )
    assert len(suggestions) == 1


def test_rejecting_a_suggestion_removes_its_gain():
    outcome = _run([GOOD_SKILL])
    rejected = outcome.suggestions[0].model_copy(update={"decision": Decision.REJECTED})
    _, before, after = rescore(
        sample_sections(), outcome.keywords, [rejected], SeniorityBand.SENIOR, today=TODAY
    )
    assert before == outcome.score_before and after == before


# --- applying decisions -------------------------------------------------


def test_only_accepted_suggestions_are_applied_and_input_is_untouched():
    sections = sample_sections()
    target = bullet_id(sections, "Mentored")
    accepted = Suggestion(
        kind=SuggestionKind.REWRITE_BULLET,
        section=SuggestionSection.EXPERIENCE,
        target_id=target,
        proposed="Coached 3 junior engineers",
        decision=Decision.ACCEPTED,
    )
    pending = Suggestion(
        kind=SuggestionKind.ADD_SKILL, section=SuggestionSection.SKILLS, proposed="Jenkins"
    )
    result = apply_decisions(sections, [accepted, pending])
    assert "Coached 3 junior engineers" in [b.text for b in result.experience[0].bullets]
    assert "Jenkins" not in result.skills
    assert "Mentored 3 junior engineers" in [b.text for b in sections.experience[0].bullets]


def test_apply_handles_skills_summary_reorder_and_stale_targets():
    sections = sample_sections()
    suggestions = [
        Suggestion(
            kind=SuggestionKind.ADD_SKILL, section=SuggestionSection.SKILLS, proposed="Redis"
        ),
        Suggestion(
            kind=SuggestionKind.ADD_SKILL, section=SuggestionSection.SKILLS, proposed="python"
        ),
        Suggestion(
            kind=SuggestionKind.REWRITE_SUMMARY,
            section=SuggestionSection.SUMMARY,
            proposed="Python backend engineer on AWS.",
        ),
        Suggestion(
            kind=SuggestionKind.REORDER_SECTION,
            section=SuggestionSection.SKILLS,
            target_id="skills",
            proposed="AWS, Docker",
        ),
        Suggestion(
            kind=SuggestionKind.REWRITE_BULLET,
            section=SuggestionSection.EXPERIENCE,
            target_id="stale-id",
            proposed="Ignored",
        ),
    ]
    result = apply_suggestions(sections, suggestions)
    assert result.skills == ["AWS", "Docker", "Python", "Flask", "PostgreSQL", "Redis"]
    assert result.summary == "Python backend engineer on AWS."
    assert result.experience == sections.experience  # stale target changed nothing


# --- rendering ----------------------------------------------------------


def test_html_is_single_column_semantic_and_escaped():
    sections = sample_sections()
    sections.contact.name = "Priya <script>alert(1)</script> Nair"
    html = render_html(sections)
    assert "<script>" not in html and "&lt;script&gt;" in html
    for forbidden in ("<table", "<img", "float:", "column-count"):
        assert forbidden not in html
    assert html.index("<h2>Summary") < html.index("<h2>Experience") < html.index("<h2>Skills")
    assert "Jan 2022 – Present" in html


def test_stub_renderer_produces_openable_docx_and_roundtrippable_pdf():
    renderer = StubDocumentRenderer()
    sections = sample_sections()
    docx = renderer.render(sections, DocumentFormat.DOCX)
    with zipfile.ZipFile(BytesIO(docx.content)) as archive:
        assert "Priya Nair" in archive.read("word/document.xml").decode()
        assert "[Content_Types].xml" in archive.namelist()
    pdf = renderer.render(sections, DocumentFormat.PDF)
    assert pdf.content.startswith(b"%PDF-") and pdf.media_type == "application/pdf"
    assert render_text(sections).splitlines()[0] == "Priya Nair"


@pytest.mark.parametrize("fmt", list(DocumentFormat))
def test_renderer_reports_extension(fmt):
    assert StubDocumentRenderer().render(sample_sections(), fmt).extension == fmt.value
