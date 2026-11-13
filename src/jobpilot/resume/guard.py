"""The fabrication guard: no suggestion may add a fact the resume lacks.

An LLM asked to "tailor" a resume will, left alone, happily add a
Kubernetes line to someone who has never used it. That is the failure
that matters here, so safety does not rest on the prompt. Every
suggestion is machine-checked against the original resume, and one that
introduces anything unsupported is dropped before the user sees it.

What is checked, and against what:

* **Numbers and dates** (metrics, years, percentages, "Q3"): every number
  in the proposed text must appear in the text being rewritten. Words
  like "doubled" or "tenfold" are quantitative claims too and follow the
  same rule.
* **Employers, schools, tools, other proper nouns**: any capitalised
  word that is not the first word of a sentence must already occur
  somewhere in the resume. This is deliberately blunt; it is cheaper to
  reject a legitimate rewrite than to let an invented employer through.
* **Job titles**: seniority and leadership words ("senior", "director",
  "founder", ...) may only appear if the resume already uses them.
* **Skills**: a job keyword may only appear in a rewrite if the resume
  already mentions it. `add_skill` is stricter: the skill must be
  *demonstrated* in a bullet, project, or summary, not merely listed.
* **Structure**: a reorder must be a permutation (nothing added or
  dropped); a bullet rewrite must target a real bullet; a summary rewrite
  needs an existing summary.

Known limits, accepted on purpose: it cannot judge whether a reworded
claim is *true* (changing "contributed to" into "led" passes), and it
rejects some harmless rewrites. Suggestions are advisory and the user
accepts each one, so the guard's job is to remove invention, not to
replace review.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from jobpilot.resume.keywords import contains_term, normalize_term, resume_text
from jobpilot.resume.models import ResumeSections, Suggestion, SuggestionKind

MAX_BULLET_CHARS = 400
MAX_SKILL_CHARS = 40

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-/']*")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_QUANTITY_WORDS = ("doubled", "tripled", "quadrupled", "halved", "tenfold")
_TITLE_WORDS = (
    "senior", "staff", "principal", "director", "vp", "head", "chief", "manager",
    "founder", "cofounder", "cto", "ceo", "architect", "intern",
)  # fmt: skip


@dataclass(frozen=True)
class GuardVerdict:
    ok: bool
    violations: tuple[str, ...] = ()


def extract_numbers(text: str) -> set[str]:
    """Numbers in `text`, normalised so "1,000" and "1000" compare equal."""

    return {m.replace(",", "").rstrip(".") for m in _NUMBER_RE.findall(text)}


def _tokens(text: str) -> list[str]:
    return [t.rstrip(".'/-") for t in _TOKEN_RE.findall(text)]


def _vocabulary(text: str) -> set[str]:
    vocab: set[str] = set()
    for token in _tokens(text):
        lowered = token.casefold()
        vocab.add(lowered)
        vocab.update(part for part in re.split(r"[-/.]", lowered) if part)
    return vocab


def _in_vocab(token: str, vocab: set[str]) -> bool:
    lowered = token.casefold().removesuffix("'s")
    parts = [p for p in re.split(r"[-/.]", lowered) if p]
    candidates = {lowered, lowered.rstrip("s")}
    return bool(candidates & vocab) or (
        bool(parts) and all(p in vocab or p.rstrip("s") in vocab for p in parts)
    )


def _entity_like_tokens(text: str) -> list[str]:
    """Capitalised or camel-cased words, ignoring each sentence's first word."""

    found = []
    for sentence in _SENTENCE_SPLIT_RE.split(text.strip()):
        for token in _tokens(sentence)[1:]:
            if token[0].isupper() or any(c.isupper() for c in token[1:]):
                found.append(token)
    return found


class FabricationGuard:
    """Checks suggestions against one specific original resume."""

    def __init__(self, original: ResumeSections, job_terms: Iterable[str] = ()) -> None:
        self._original = original
        self._job_terms = [normalize_term(t) for t in job_terms]
        # Everything the resume says, including facts outside the
        # sections we rewrite (contact name, dates, GPA), so that
        # repeating a true fact is never flagged.
        extra = [original.contact.name, original.contact.location or ""]
        extra += [f"{j.start} {j.end or ''}" for j in original.experience]
        extra += [f"{e.start or ''} {e.end or ''} {e.score or ''}" for e in original.education]
        self._all_text = "\n".join([resume_text(original), *extra])
        self._evidence_text = resume_text(original, include_skills=False)
        self._vocab = _vocabulary(self._all_text)

    def check(self, suggestion: Suggestion) -> GuardVerdict:
        kind = suggestion.kind
        if kind is SuggestionKind.REWRITE_BULLET:
            violations = self._check_bullet(suggestion)
        elif kind is SuggestionKind.REWRITE_SUMMARY:
            violations = self._check_summary(suggestion)
        elif kind is SuggestionKind.ADD_SKILL:
            violations = self._check_skill(suggestion)
        else:
            violations = self._check_reorder(suggestion)
        return GuardVerdict(ok=not violations, violations=tuple(violations))

    def filter(
        self, suggestions: Iterable[Suggestion]
    ) -> tuple[list[Suggestion], list[tuple[Suggestion, GuardVerdict]]]:
        """Split into `(kept, rejected_with_reasons)`."""

        kept, rejected = [], []
        for suggestion in suggestions:
            verdict = self.check(suggestion)
            if verdict.ok:
                kept.append(suggestion)
            else:
                rejected.append((suggestion, verdict))
        return kept, rejected

    # --- per kind ------------------------------------------------------

    def _check_bullet(self, s: Suggestion) -> list[str]:
        original = self._find_bullet_text(s.target_id)
        if original is None:
            return ["target bullet does not exist in the resume"]
        return self._check_rewrite(s, original, max_chars=MAX_BULLET_CHARS)

    def _check_summary(self, s: Suggestion) -> list[str]:
        if not self._original.summary:
            return ["the resume has no summary to rewrite"]
        return self._check_rewrite(s, self._original.summary, max_chars=MAX_BULLET_CHARS)

    def _check_skill(self, s: Suggestion) -> list[str]:
        skill = s.proposed.strip()
        if len(skill) > MAX_SKILL_CHARS or re.search(r"[.!?]\s", skill) or "," in skill:
            return ["a skill must be a single short term"]
        if any(normalize_term(skill) == normalize_term(x) for x in self._original.skills):
            return ["skill is already listed"]
        if not contains_term(self._evidence_text, skill):
            return ["skill is not demonstrated anywhere else in the resume"]
        return []

    def _check_reorder(self, s: Suggestion) -> list[str]:
        if s.target_id == "skills":
            current = list(self._original.skills)
        elif s.target_id == "projects":
            current = [p.name for p in self._original.projects]
        else:
            return ["only the skills and projects sections can be reordered"]
        proposed = [p.strip() for p in s.proposed.split(",") if p.strip()]
        if sorted(map(str.casefold, proposed)) != sorted(map(str.casefold, current)):
            return ["a reorder must contain exactly the existing items"]
        return []

    # --- shared rewrite checks ---------------------------------------------

    def _check_rewrite(self, s: Suggestion, original: str, *, max_chars: int) -> list[str]:
        text = s.proposed.strip()
        violations: list[str] = []
        if text.casefold() == original.strip().casefold():
            violations.append("the proposed text does not change anything")
        if len(text) > max_chars:
            violations.append(f"the proposed text is longer than {max_chars} characters")

        new_numbers = extract_numbers(text) - extract_numbers(original)
        if new_numbers:
            violations.append(f"introduces numbers not in the original: {sorted(new_numbers)}")

        lowered_original, lowered = original.casefold(), text.casefold()
        for word in _QUANTITY_WORDS:
            if re.search(rf"\b{word}\b", lowered) and not re.search(
                rf"\b{word}\b", lowered_original
            ):
                violations.append(f"makes a quantitative claim ('{word}') not in the original")

        for title in _TITLE_WORDS:
            pattern = rf"\b{title}\b"
            if re.search(pattern, lowered) and not re.search(pattern, self._all_text.casefold()):
                violations.append(f"introduces a job title word not in the resume: '{title}'")

        unknown = sorted(
            {
                t
                for t in _entity_like_tokens(text)
                if not _in_vocab(t, self._vocab) and not contains_term(self._all_text, t)
            }
        )
        if unknown:
            violations.append(f"introduces names not in the resume: {unknown}")

        for term in self._job_terms:
            if contains_term(text, term) and not contains_term(self._all_text, term):
                violations.append(f"mentions '{term}', which the resume never does")
        for term in s.keywords_added:
            if not contains_term(self._all_text, term):
                violations.append(f"claims to add '{term}', which the resume does not support")
        return violations

    def _find_bullet_text(self, bullet_id: str | None) -> str | None:
        if bullet_id is None:
            return None
        for entry in [*self._original.experience, *self._original.projects]:
            for bullet in entry.bullets:
                if bullet.id == bullet_id:
                    return bullet.text
        return None
