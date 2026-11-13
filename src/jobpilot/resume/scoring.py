"""A deterministic 0-100 match score between a resume and a job.

Pure functions, no LLM, no I/O: given the same resume and keywords the
score is always the same, so a user can see exactly why it moved when
they accept a suggestion, and tests can pin it down.

    score = 100 * weighted mean of
        required keyword coverage   (weight 0.55)
        preferred keyword coverage  (weight 0.15)
        seniority fit               (weight 0.15)
        recency of relevant work    (weight 0.15)

Required keywords dominate because they are what a screener (human or
ATS) filters on. A component with nothing to measure (a job that lists
no preferred keywords) is dropped and the remaining weights are
renormalised, rather than counted as a free 100%.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from jobpilot.models import SENIORITY_ORDER, SeniorityBand, seniority_band_for_years
from jobpilot.resume.keywords import contains_term, coverage_fraction
from jobpilot.resume.models import KeywordEntry, KeywordImportance, ResumeSections

_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}
_PRESENT = {"present", "current", "now", "ongoing", "today"}


@dataclass(frozen=True)
class ScoreWeights:
    required: float = 0.55
    preferred: float = 0.15
    seniority: float = 0.15
    recency: float = 0.15


@dataclass(frozen=True)
class ScoreBreakdown:
    """The score and the components behind it, each in [0, 1] (or `None`)."""

    required: float | None
    preferred: float | None
    seniority: float
    recency: float
    total: float  # 0-100, one decimal


# --- dates -----------------------------------------------------------------


def parse_year_month(text: str | None, *, today: date) -> tuple[int, int] | None:
    """Best-effort `(year, month)` from "Jun 2021", "06/2021", "2021-06", "2021", "Present"."""

    if text is None:
        return None
    lowered = text.casefold().strip()
    if lowered in _PRESENT:
        return today.year, today.month
    year_match = re.search(r"\b(19|20)\d{2}\b", lowered)
    if not year_match:
        return None
    year = int(year_match.group())
    month = 1
    word = re.search(r"\b([a-z]{3})[a-z]*\b", lowered)
    if word and word.group(1) in _MONTHS:
        month = _MONTHS[word.group(1)]
    else:
        numeric = re.search(
            r"\b(0?[1-9]|1[0-2])\s*[/-]\s*(?:19|20)\d{2}\b|(?:19|20)\d{2}\s*[/-]\s*(0?[1-9]|1[0-2])\b",
            lowered,
        )
        if numeric:
            month = int(numeric.group(1) or numeric.group(2))
    return year, month


def _month_index(ym: tuple[int, int]) -> int:
    return ym[0] * 12 + (ym[1] - 1)


def _experience_intervals(sections: ResumeSections, today: date) -> list[tuple[int, int]]:
    intervals = []
    for job in sections.experience:
        start = parse_year_month(job.start, today=today)
        end = parse_year_month(job.end, today=today) if job.end else (today.year, today.month)
        if start is None or end is None:
            continue
        lo, hi = _month_index(start), _month_index(end)
        if hi >= lo:
            intervals.append((lo, hi))
    return intervals


def estimate_years_experience(sections: ResumeSections, *, today: date | None = None) -> float:
    """Total years across roles, counting overlapping roles once."""

    today = today or datetime.now(UTC).date()
    merged: list[list[int]] = []
    for lo, hi in sorted(_experience_intervals(sections, today)):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return sum(hi - lo for lo, hi in merged) / 12


def candidate_band(sections: ResumeSections, *, today: date | None = None) -> SeniorityBand:
    """Seniority implied by years of experience. Never `INTERN` (see models)."""

    return seniority_band_for_years(estimate_years_experience(sections, today=today))


# --- components ------------------------------------------------------------


def seniority_fit(candidate: SeniorityBand, job: SeniorityBand | None) -> float:
    """How well the candidate's level fits the job's level, in [0, 1].

    Asymmetric on purpose. Being one level above a job costs a little
    (0.75: still plausible, maybe overqualified); being one level below
    costs more (0.6) and two below almost rules the application out
    (0.2). An unknown job level (pasted description) is a neutral 0.5,
    the same convention `search.ranking` uses.
    """

    if job is None:
        return 0.5
    gap = SENIORITY_ORDER[job] - SENIORITY_ORDER[candidate]  # >0: job is a stretch
    if gap == 0:
        return 1.0
    if gap < 0:
        return max(0.0, 1.0 + gap * 0.25)
    return max(0.0, 1.0 - gap * 0.4)


def recency_of_relevant_experience(
    sections: ResumeSections, terms: Sequence[str], *, today: date | None = None
) -> float:
    """How recently the candidate did work that mentions the job's keywords.

    Full marks for relevant work ending within 12 months (or ongoing),
    then exponential decay with a 24-month half-life. If no job
    mentions a keyword but a project does, 0.5: real but undated
    evidence. No terms at all is a neutral 0.5; relevance cannot be
    judged.
    """

    if not terms:
        return 0.5
    today = today or datetime.now(UTC).date()
    now_index = _month_index((today.year, today.month))
    best_gap: int | None = None
    for job in sections.experience:
        blob = " ".join([job.title, *(b.text for b in job.bullets)])
        if not any(contains_term(blob, t) for t in terms):
            continue
        end = parse_year_month(job.end, today=today) if job.end else (today.year, today.month)
        if end is None:
            continue
        gap = max(0, now_index - _month_index(end))
        best_gap = gap if best_gap is None else min(best_gap, gap)
    if best_gap is not None:
        return 1.0 if best_gap <= 12 else 0.5 ** ((best_gap - 12) / 24)
    project_text = " ".join(
        [p.name for p in sections.projects]
        + [b.text for p in sections.projects for b in p.bullets]
        + [t for p in sections.projects for t in p.tech]
    )
    return 0.5 if any(contains_term(project_text, t) for t in terms) else 0.0


# --- combination -----------------------------------------------------------


def score_match(
    sections: ResumeSections,
    entries: Sequence[KeywordEntry],
    job_band: SeniorityBand | None,
    *,
    after: bool = False,
    today: date | None = None,
    weights: ScoreWeights | None = None,
) -> ScoreBreakdown:
    """Score `sections` against the job described by `entries`.

    `after=True` reads each entry's `covered_after` flag instead of
    `found_in_resume`; the caller passes the sections with accepted
    suggestions applied so that the recency component sees them too.
    """

    weights = weights or ScoreWeights()
    required = coverage_fraction(entries, KeywordImportance.REQUIRED, after=after)
    preferred = coverage_fraction(entries, KeywordImportance.PREFERRED, after=after)
    seniority = seniority_fit(candidate_band(sections, today=today), job_band)
    recency = recency_of_relevant_experience(sections, [e.term for e in entries], today=today)

    components = [
        (weights.required, required),
        (weights.preferred, preferred),
        (weights.seniority, seniority),
        (weights.recency, recency),
    ]
    present = [(w, v) for w, v in components if v is not None]
    total_weight = sum(w for w, _ in present)
    total = 100 * sum(w * v for w, v in present) / total_weight if total_weight else 0.0
    return ScoreBreakdown(required, preferred, seniority, recency, round(total, 1))


__all__ = [
    "ScoreBreakdown",
    "ScoreWeights",
    "candidate_band",
    "estimate_years_experience",
    "parse_year_month",
    "recency_of_relevant_experience",
    "score_match",
    "seniority_fit",
]
