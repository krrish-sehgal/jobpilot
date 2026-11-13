"""Job keywords: extract, normalise, and measure coverage in a resume.

Matching "Postgres" in a job against "PostgreSQL" in a resume, or "k8s"
against "Kubernetes", is the difference between a score that looks right
to a person and one that does not. Everything here is therefore built
around one canonical form per term (`normalize_term`) and a matcher that
understands the aliases of that canonical form (`contains_term`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from jobpilot.errors import LLMProviderError, ResumeParseError
from jobpilot.integrations.llm import LLMClient
from jobpilot.logging import get_logger
from jobpilot.resume.models import KeywordEntry, KeywordImportance, ResumeSections
from jobpilot.resume.parser import parse_json_object
from jobpilot.resume.prompts import KEYWORD_SYSTEM_PROMPT

logger = get_logger(__name__)

#: alias -> canonical term. Canonical forms are what we store and show.
SYNONYMS: dict[str, str] = {
    "js": "javascript",
    "ecmascript": "javascript",
    "ts": "typescript",
    "k8s": "kubernetes",
    "golang": "go",
    "postgres": "postgresql",
    "psql": "postgresql",
    "mongo": "mongodb",
    "node": "node.js",
    "nodejs": "node.js",
    "node js": "node.js",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "amazon web services": "aws",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "ml": "machine learning",
    "llms": "llm",
    "large language models": "llm",
    "dotnet": ".net",
    "c sharp": "c#",
    "cicd": "ci/cd",
    "restful": "rest",
    "rest api": "rest",
    "rest apis": "rest",
    "restful api": "rest",
    "sklearn": "scikit-learn",
}

_MAX_REQUIRED = 20
_MAX_PREFERRED = 12
_EDGE_PUNCTUATION = " \t\n\r,;:()[]{}\"'"


def normalize_term(term: str) -> str:
    """Canonical form of a skill or keyword: case-folded, trimmed, de-aliased.

    Leading dots and trailing `+`/`#` are kept on purpose (".net",
    "c++", "c#"); a trailing sentence period is not.
    """

    cleaned = re.sub(r"\s+", " ", term.casefold().strip(_EDGE_PUNCTUATION))
    cleaned = cleaned.rstrip(".")
    return SYNONYMS.get(cleaned, cleaned)


def _build_aliases() -> dict[str, tuple[str, ...]]:
    aliases: dict[str, set[str]] = {}
    for alias, canonical in SYNONYMS.items():
        aliases.setdefault(canonical, {canonical}).add(alias)
    return {
        canonical: tuple(sorted(names, key=len, reverse=True))
        for canonical, names in aliases.items()
    }


_ALIASES = _build_aliases()


def _pattern_for(alias: str) -> re.Pattern[str]:
    # A term must not be glued to other word characters on either side
    # ("java" must not match "javascript"), and "node" must not match the
    # first half of "node.js" (hence the `.` followed by alphanumeric guard).
    return re.compile(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9+#])(?!\.[a-z0-9])")


def contains_term(text: str, term: str) -> bool:
    """True if `text` mentions `term` or any alias of its canonical form."""

    canonical = normalize_term(term)
    lowered = text.casefold()
    names = _ALIASES.get(canonical, (canonical,))
    return any(_pattern_for(name).search(lowered) for name in names)


# ---------------------------------------------------------------------------
# Resume text views
# ---------------------------------------------------------------------------


def resume_text(sections: ResumeSections, *, include_skills: bool = True) -> str:
    """Everything in the resume a keyword could legitimately appear in.

    Contact details are excluded: an email address or city is not
    evidence of a skill. `include_skills=False` gives the "evidence
    elsewhere" view the fabrication guard needs for `add_skill`: a skill
    listed only in the skills section has not been demonstrated.
    """

    parts: list[str] = []
    if sections.summary:
        parts.append(sections.summary)
    for job in sections.experience:
        parts += [job.company, job.title, *(b.text for b in job.bullets)]
    for edu in sections.education:
        parts += [edu.institution, edu.degree]
    for project in sections.projects:
        parts += [project.name, *(b.text for b in project.bullets), *project.tech]
    if include_skills:
        parts += sections.skills
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JobKeywords:
    required: tuple[str, ...]
    preferred: tuple[str, ...]
    job_title: str | None = None
    company: str | None = None


def _dedupe(terms: Iterable[str], *, exclude: Iterable[str] = (), limit: int) -> tuple[str, ...]:
    seen: dict[str, None] = dict.fromkeys(exclude)
    for term in terms:
        normalized = normalize_term(str(term))
        if normalized and normalized not in seen:
            seen[normalized] = None
    kept = [t for t in seen if t not in set(exclude)]
    return tuple(kept[:limit])


def extract_job_keywords(
    llm: LLMClient, *, title: str, description: str, skills: Iterable[str] = ()
) -> JobKeywords:
    """Required and preferred keywords for a job.

    Structured `JobRecord.skills` (already validated at enrichment) are
    always treated as required. The LLM reads the description to add
    terms the structured list missed and to split the rest into
    required versus preferred. If the LLM is unavailable but structured
    skills exist, we degrade to those rather than failing the whole
    tailoring; with neither, there is nothing to tailor against.
    """

    structured = _dedupe(skills, limit=_MAX_REQUIRED)
    try:
        response = llm.complete(
            system_prompt=KEYWORD_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"<job>\nTitle: {title}\n\n{description[:12000]}\n</job>",
                }
            ],
            temperature=0.0,
        )
        payload = parse_json_object(response.get("content"))
        llm_required = [str(t) for t in payload.get("required") or []]
        llm_preferred = [str(t) for t in payload.get("preferred") or []]
        job_title = payload.get("job_title") or None
        company = payload.get("company") or None
    except (LLMProviderError, ResumeParseError) as exc:
        if not structured:
            raise ResumeParseError("could not identify the requirements in this job") from exc
        logger.warning("keyword_extraction_degraded", error=str(exc))
        return JobKeywords(required=structured, preferred=())

    required = _dedupe([*structured, *llm_required], limit=_MAX_REQUIRED)
    preferred = _dedupe(llm_preferred, exclude=required, limit=_MAX_PREFERRED)
    if not required and not preferred:
        raise ResumeParseError("could not identify the requirements in this job")
    return JobKeywords(required, preferred, job_title, company)


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def compute_coverage(keywords: JobKeywords, sections: ResumeSections) -> list[KeywordEntry]:
    """One entry per keyword, flagged by whether the resume already has it.

    `covered_after` starts equal to `found_in_resume`; tailoring updates
    it once it knows which suggestions survived the fabrication guard.
    """

    text = resume_text(sections)
    entries = []
    for importance, terms in (
        (KeywordImportance.REQUIRED, keywords.required),
        (KeywordImportance.PREFERRED, keywords.preferred),
    ):
        for term in terms:
            found = contains_term(text, term)
            entries.append(
                KeywordEntry(
                    term=term, importance=importance, found_in_resume=found, covered_after=found
                )
            )
    return entries


def coverage_fraction(
    entries: Iterable[KeywordEntry],
    importance: KeywordImportance,
    *,
    after: bool = False,
) -> float | None:
    """Share of keywords of one importance that are present; `None` if there are none."""

    relevant = [e for e in entries if e.importance == importance]
    if not relevant:
        return None
    hits = sum(1 for e in relevant if (e.covered_after if after else e.found_in_resume))
    return hits / len(relevant)
