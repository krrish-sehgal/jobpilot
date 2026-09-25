"""
Text-to-vector embedding.

This is the piece that turns a description into a fixed-length list of
numbers so that "closeness in meaning" can be measured as distance
between vectors. See docs/architecture.md for the more interesting
idea this project builds on top of embeddings: embedding an *ideal
candidate description* rather than the job posting itself.
"""

from __future__ import annotations

EMBEDDING_DIMENSIONS = 8
"""Kept tiny on purpose for a demo — a real embedding model would use
hundreds or thousands of dimensions."""


def embed_text(text: str) -> list[float]:
    """Return a fixed-length vector representing `text`.

    A real implementation would call an embedding model. This demo
    returns a fixed, fake vector regardless of input, since nothing
    here should be mistaken for a working similarity search.
    """
    return [0.0] * EMBEDDING_DIMENSIONS


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """Standard cosine similarity between two equal-length vectors,
    returning a value in [-1, 1]. This one small piece of math is real
    (it has no external dependency to stub out) — everything that
    produces the vectors it compares is faked elsewhere.
    """
    if len(vector_a) != len(vector_b):
        raise ValueError("vectors must be the same length")
    dot = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = sum(a * a for a in vector_a) ** 0.5
    norm_b = sum(b * b for b in vector_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
