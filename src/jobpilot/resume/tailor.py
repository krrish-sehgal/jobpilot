"""Resume tailoring: generate suggestions, guard them, score the result.

The pipeline for one (resume, job) pair:

1. measure keyword coverage and the "before" score,
2. ask the LLM for suggestions (`generate_suggestions`),
3. drop every suggestion the fabrication guard rejects,
4. apply the survivors to a copy of the resume and compute the "after"
   score as if the user accepted all of them.

Step 4 is what the UI shows as the potential gain; the user's actual
accept/reject choices later re-run `rescore` with only the suggestions
they have not rejected.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

from pydantic import ValidationError

from jobpilot.integrations.llm import LLMClient
from jobpilot.logging import get_logger
from jobpilot.models import SeniorityBand
from jobpilot.resume.apply import apply_suggestions
from jobpilot.resume.guard import FabricationGuard, GuardVerdict
from jobpilot.resume.keywords import JobKeywords, compute_coverage, contains_term, resume_text
from jobpilot.resume.models import (
    Decision,
    KeywordEntry,
    ResumeSections,
    Suggestion,
    SuggestionKind,
)
from jobpilot.resume.parser import parse_json_object
from jobpilot.resume.prompts import TAILOR_SYSTEM_PROMPT
from jobpilot.resume.scoring import score_match

logger = get_logger(__name__)

MAX_SUGGESTIONS = 12


@dataclass
class TailoringOutcome:
    keywords: list[KeywordEntry]
    suggestions: list[Suggestion]
    score_before: float
    score_after: float
    rejected: list[tuple[Suggestion, GuardVerdict]] = field(default_factory=list)


def tailor_resume(
    llm: LLMClient,
    sections: ResumeSections,
    keywords: JobKeywords,
    *,
    job_title: str,
    company: str | None,
    job_band: SeniorityBand | None,
    today: date | None = None,
) -> TailoringOutcome:
    entries = compute_coverage(keywords, sections)
    candidates = generate_suggestions(
        llm, sections, keywords, entries, job_title=job_title, company=company
    )
    guard = FabricationGuard(sections, [*keywords.required, *keywords.preferred])
    kept, rejected = guard.filter(candidates)
    for suggestion, verdict in rejected:
        logger.info(
            "suggestion_rejected_by_guard",
            kind=suggestion.kind.value,
            violations=list(verdict.violations),
        )
    entries, before, after = rescore(sections, entries, kept, job_band, today=today)
    return TailoringOutcome(entries, kept, before, after, rejected)


def rescore(
    sections: ResumeSections,
    entries: list[KeywordEntry],
    suggestions: list[Suggestion],
    job_band: SeniorityBand | None,
    *,
    today: date | None = None,
) -> tuple[list[KeywordEntry], float, float]:
    """Recompute `covered_after` and both scores.

    "After" assumes every suggestion that is not rejected will be
    applied: pending ones count as the potential gain, accepted ones as
    the realised gain. `found_in_resume` and `score_before` always
    describe the original resume and never change.
    """

    surviving = [s for s in suggestions if s.decision is not Decision.REJECTED]
    after_sections = apply_suggestions(sections, surviving)
    after_text = resume_text(after_sections)
    updated = [
        e.model_copy(update={"covered_after": contains_term(after_text, e.term)}) for e in entries
    ]
    before = score_match(sections, updated, job_band, today=today).total
    after = score_match(after_sections, updated, job_band, today=today).total
    return updated, before, after


def generate_suggestions(
    llm: LLMClient,
    sections: ResumeSections,
    keywords: JobKeywords,
    entries: list[KeywordEntry],
    *,
    job_title: str,
    company: str | None,
) -> list[Suggestion]:
    """Ask the LLM for suggestions and parse them leniently, one by one.

    A single malformed suggestion is skipped (and logged); it does not
    sink the others. `original` is filled in from the resume, never
    taken from the model, so the diff the user sees is always accurate.
    """

    request = {
        "job": {
            "title": job_title,
            "company": company,
            "required": list(keywords.required),
            "preferred": list(keywords.preferred),
            "missing": [e.term for e in entries if not e.found_in_resume],
        },
        "resume": sections.model_dump(mode="json"),
    }
    response = llm.complete(
        system_prompt=TAILOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(request)}],
        temperature=0.2,
    )
    payload = parse_json_object(response.get("content"))
    raw_items = payload.get("suggestions")
    if not isinstance(raw_items, list):
        return []

    suggestions: list[Suggestion] = []
    seen: set[tuple[str, str | None]] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            suggestion = Suggestion.model_validate(
                {**raw, "original": None, "decision": Decision.PENDING}
            )
        except ValidationError:
            logger.info("suggestion_malformed", raw=str(raw)[:200])
            continue
        suggestion.original = _original_text(sections, suggestion)
        key = (suggestion.kind.value, suggestion.target_id or suggestion.proposed.casefold())
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(suggestion)
        if len(suggestions) >= MAX_SUGGESTIONS:
            break
    return suggestions


def _original_text(sections: ResumeSections, suggestion: Suggestion) -> str | None:
    if suggestion.kind is SuggestionKind.REWRITE_SUMMARY:
        return sections.summary
    if suggestion.kind is SuggestionKind.REWRITE_BULLET:
        for entry in [*sections.experience, *sections.projects]:
            for bullet in entry.bullets:
                if bullet.id == suggestion.target_id:
                    return bullet.text
    if suggestion.kind is SuggestionKind.REORDER_SECTION:
        if suggestion.target_id == "skills":
            return ", ".join(sections.skills)
        if suggestion.target_id == "projects":
            return ", ".join(p.name for p in sections.projects)
    return None
