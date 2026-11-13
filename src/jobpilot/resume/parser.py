"""Plain resume text -> `ResumeSections`.

One LLM call with a strict JSON prompt, validated by pydantic. The
parser never repairs a bad reply: if the model returns something that
is not valid JSON of the right shape, the resume is marked failed with a
reason the user can act on (re-upload, try a DOCX), rather than showing a
half-understood resume that tailoring would then build on.
"""

from __future__ import annotations

import json
import re
from uuid import NAMESPACE_URL, uuid5

from pydantic import ValidationError

from jobpilot.errors import LLMProviderError, ResumeParseError
from jobpilot.integrations.llm import LLMClient
from jobpilot.resume.models import Bullet, ResumeSections
from jobpilot.resume.prompts import PARSE_SYSTEM_PROMPT

#: Resumes longer than this are truncated before the LLM call. Two dense
#: pages are ~8k characters; the cap leaves room without letting a
#: pathological upload run up an unbounded bill.
MAX_PARSE_CHARS = 30_000

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(content: str | None) -> dict:
    """Decode an LLM reply that should be a single JSON object.

    Tolerates exactly one harmless deviation, a markdown code fence
    around the JSON, because models add it often despite instructions.
    Anything else raises `ResumeParseError`.
    """

    if not content or not content.strip():
        raise ResumeParseError("the model returned an empty reply")
    cleaned = _FENCE_RE.sub("", content.strip())
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ResumeParseError(f"the model reply was not valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ResumeParseError("the model reply must be a JSON object")
    return payload


def parse_resume(llm: LLMClient, text: str) -> ResumeSections:
    """Structure `text` into sections with stable ids on every bullet."""

    try:
        response = llm.complete(
            system_prompt=PARSE_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"<resume>\n{text[:MAX_PARSE_CHARS]}\n</resume>"}
            ],
            temperature=0.0,
        )
    except LLMProviderError as exc:
        raise ResumeParseError(f"the language model was unavailable: {exc}") from exc

    payload = parse_json_object(response.get("content"))
    try:
        sections = ResumeSections.model_validate(payload)
    except ValidationError as exc:
        raise ResumeParseError(
            f"the parsed resume had an unexpected shape: {exc.error_count()} errors"
        ) from exc
    if not sections.contact.name.strip() and not sections.experience and not sections.education:
        raise ResumeParseError("no resume content could be recognised in the file")
    return assign_ids(sections)


def _stable_id(prefix: str, *parts: object) -> str:
    """A deterministic UUID derived from where an item sits and what it says.

    "Stable" means re-parsing the same text yields the same ids, so a
    suggestion generated against one parse still resolves after a
    re-parse. UUIDs (rather than `exp-1-b2`) keep the id format uniform
    with the rest of the API, which promises UUID strings everywhere.
    """

    return str(uuid5(NAMESPACE_URL, "jobpilot:resume:" + prefix + ":" + "|".join(map(str, parts))))


def assign_ids(sections: ResumeSections) -> ResumeSections:
    """Return a copy of `sections` with ids on every entry and bullet."""

    result = sections.model_copy(deep=True)
    for i, job in enumerate(result.experience):
        job.id = _stable_id("exp", i, job.company, job.title, job.start)
        job.bullets = _with_ids(job.bullets, job.id)
    for i, edu in enumerate(result.education):
        edu.id = _stable_id("edu", i, edu.institution, edu.degree)
    for i, project in enumerate(result.projects):
        project.id = _stable_id("proj", i, project.name)
        project.bullets = _with_ids(project.bullets, project.id)
    return result


def _with_ids(bullets: list[Bullet], parent_id: str) -> list[Bullet]:
    return [
        Bullet(id=_stable_id("bullet", parent_id, i, bullet.text), text=bullet.text.strip())
        for i, bullet in enumerate(bullets)
        if bullet.text.strip()
    ]
