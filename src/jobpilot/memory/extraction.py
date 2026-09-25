"""Background extraction of durable user facts from conversation history."""

from __future__ import annotations

import json
from uuid import UUID

from jobpilot.errors import EnrichmentSchemaError
from jobpilot.integrations.llm import LLMClient
from jobpilot.memory.prompts import MEMORY_EXTRACTION_SYSTEM_PROMPT
from jobpilot.models import Message, UserFact

_VALID_CATEGORIES = {"background", "constraint", "preference", "goal"}


def extract_facts(llm: LLMClient, user_id: UUID, messages: list[Message]) -> list[UserFact]:
    """Extract durable facts from a window of conversation history.

    `messages` should be ordered oldest-first. Returns an empty list
    if the window contains no durable facts — this is a normal,
    expected outcome, not an error.
    """

    if not messages:
        return []

    transcript = "\n".join(
        f"{'User' if m.direction.value == 'inbound' else 'Assistant'}: {m.body}" for m in messages
    )
    response = llm.complete(
        system_prompt=MEMORY_EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript}],
        temperature=0.0,
    )

    content = response.get("content")
    if not content:
        raise EnrichmentSchemaError("memory extraction returned no content")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise EnrichmentSchemaError(f"memory extraction output was not valid JSON: {exc}") from exc

    if not isinstance(payload, list):
        raise EnrichmentSchemaError("memory extraction output must be a JSON array")

    facts: list[UserFact] = []
    last_message_id = messages[-1].id
    for item in payload:
        category = item.get("category", "general")
        if category not in _VALID_CATEGORIES:
            raise EnrichmentSchemaError(
                f"memory extraction returned invalid category: {category!r}"
            )
        facts.append(
            UserFact(
                user_id=user_id,
                fact_text=item["fact_text"].strip(),
                category=category,
                confidence=float(item.get("confidence", 0.8)),
                source_message_id=last_message_id,
            )
        )
    return facts
