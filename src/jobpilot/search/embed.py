"""Embedding helpers.

`embed_candidate_profile` is the one call site that matters: it embeds
`JobRecord.candidate_profile_text` (the ideal-candidate description),
not the raw job description. See `docs/architecture.md` for why that
distinction is the core idea behind JobPilot's matching.
"""

from __future__ import annotations

import math

from jobpilot.integrations.llm import LLMClient
from jobpilot.models import JobRecord


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors, clamped to [0, 1].

    Embeddings from `FakeLLMClient` and most real embedding models are
    close to unit-normalized already; clamping guards against floating
    point drift pushing a near-1.0 result slightly over 1.0, or a
    near-orthogonal pair slightly negative in a context (this scoring
    pipeline) that expects a [0, 1] similarity, not [-1, 1].
    """

    if len(a) != len(b):
        raise ValueError("vectors must have the same dimensionality")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    raw = dot / (norm_a * norm_b)
    # Map [-1, 1] -> [0, 1] rather than hard-clamping negatives to 0,
    # so an oppositely-worded profile still ranks below an unrelated
    # (near-zero similarity) one instead of tying with it.
    return max(0.0, min(1.0, (raw + 1) / 2))


def embed_candidate_profile(llm: LLMClient, job: JobRecord) -> list[float]:
    """Embed a job's ideal-candidate description."""

    vectors = llm.embed([job.candidate_profile_text])
    return vectors[0]


def embed_query(llm: LLMClient, query_text: str) -> list[float]:
    """Embed a user-facing search query or self-description."""

    vectors = llm.embed([query_text])
    return vectors[0]
