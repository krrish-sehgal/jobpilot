"""Semantic retrieval over stored user facts.

Facts are embedded at write time (`remember`) and compared by cosine
similarity at read time (`recall`), so retrieval works by meaning
("wants to stay technical" matching a query about "individual
contributor roles") rather than requiring keyword overlap.
"""

from __future__ import annotations

from uuid import UUID

from jobpilot.db.repositories.users import UserFactRepository
from jobpilot.integrations.llm import LLMClient
from jobpilot.models import UserFact
from jobpilot.search.embed import cosine_similarity


class MemoryStore:
    def __init__(self, llm: LLMClient, facts: UserFactRepository) -> None:
        self._llm = llm
        self._facts = facts
        self._embeddings: dict[str, list[float]] = {}

    def remember(self, fact: UserFact) -> UserFact:
        saved = self._facts.save(fact)
        self._embeddings[str(saved.id)] = self._llm.embed([saved.fact_text])[0]
        return saved

    def recall(self, user_id: UUID, query: str, *, limit: int = 5) -> list[UserFact]:
        """Return up to `limit` facts for `user_id`, most similar to `query` first."""

        facts = self._facts.list_for_user(user_id)
        if not facts:
            return []

        query_vector = self._llm.embed([query])[0]
        scored = []
        for fact in facts:
            fact_id = str(fact.id)
            vector = self._embeddings.get(fact_id)
            if vector is None:
                vector = self._llm.embed([fact.fact_text])[0]
                self._embeddings[fact_id] = vector
            similarity = cosine_similarity(query_vector, vector)
            scored.append((similarity, fact))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [fact for _similarity, fact in scored[:limit]]
