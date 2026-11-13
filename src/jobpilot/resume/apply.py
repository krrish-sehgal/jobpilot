"""Apply tailoring suggestions to a resume, producing a new resume.

Pure functions: the input `ResumeSections` is never mutated. A
suggestion whose target no longer exists (the resume was re-parsed since)
is skipped rather than raising, so a stale decision can never corrupt
or block an export.
"""

from __future__ import annotations

from collections.abc import Iterable

from jobpilot.resume.keywords import normalize_term
from jobpilot.resume.models import Decision, ResumeSections, Suggestion, SuggestionKind


def apply_suggestions(
    sections: ResumeSections, suggestions: Iterable[Suggestion]
) -> ResumeSections:
    """Return a copy of `sections` with every given suggestion applied, in order."""

    result = sections.model_copy(deep=True)
    for suggestion in suggestions:
        if suggestion.kind is SuggestionKind.REWRITE_BULLET:
            _rewrite_bullet(result, suggestion)
        elif suggestion.kind is SuggestionKind.REWRITE_SUMMARY:
            if result.summary:
                result.summary = suggestion.proposed.strip()
        elif suggestion.kind is SuggestionKind.ADD_SKILL:
            _add_skill(result, suggestion.proposed.strip())
        elif suggestion.kind is SuggestionKind.REORDER_SECTION:
            _reorder(result, suggestion)
    return result


def apply_decisions(sections: ResumeSections, suggestions: Iterable[Suggestion]) -> ResumeSections:
    """Apply only the suggestions the user accepted. Used for export."""

    return apply_suggestions(sections, (s for s in suggestions if s.decision is Decision.ACCEPTED))


def _rewrite_bullet(sections: ResumeSections, suggestion: Suggestion) -> None:
    for entry in [*sections.experience, *sections.projects]:
        for bullet in entry.bullets:
            if bullet.id == suggestion.target_id:
                bullet.text = suggestion.proposed.strip()
                return


def _add_skill(sections: ResumeSections, skill: str) -> None:
    if all(normalize_term(skill) != normalize_term(existing) for existing in sections.skills):
        sections.skills.append(skill)


def _reorder(sections: ResumeSections, suggestion: Suggestion) -> None:
    order = [p.strip().casefold() for p in suggestion.proposed.split(",") if p.strip()]
    rank = {name: i for i, name in enumerate(order)}
    if suggestion.target_id == "skills":
        sections.skills.sort(key=lambda s: rank.get(s.casefold(), len(rank)))
    elif suggestion.target_id == "projects":
        sections.projects.sort(key=lambda p: rank.get(p.name.casefold(), len(rank)))
