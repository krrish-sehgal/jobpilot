"""Content hashing for posting deduplication.

The same job posting frequently reappears across scrape cycles: a
company re-posts it, an ATS platform assigns a new listing id on
renewal, or two different platforms mirror the same posting. Instead
of deduplicating on `(source_platform, source_listing_id)` — which
misses all of the above — JobPilot hashes normalized posting content
and treats an identical hash as the same posting regardless of where
or when it was seen.
"""

from __future__ import annotations

import hashlib
import re

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCTUATION_RE = re.compile(r"[^\w\s]")


def normalize_for_hashing(text: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace.

    This is deliberately aggressive: it exists only to make hashing
    robust to trivial formatting differences (extra whitespace,
    smart quotes, trailing punctuation), not to produce readable text.
    """

    lowered = text.strip().lower()
    no_punct = _PUNCTUATION_RE.sub(" ", lowered)
    return _WHITESPACE_RE.sub(" ", no_punct).strip()


def content_hash(title: str, company: str, description: str) -> str:
    """Compute a stable SHA-256 hex digest identifying a posting's content.

    Fields are normalized and joined with a delimiter unlikely to
    appear in normalized text, so `("a", "b c")` and `("a b", "c")`
    cannot collide.
    """

    parts = [
        normalize_for_hashing(title),
        normalize_for_hashing(company),
        normalize_for_hashing(description),
    ]
    joined = "\x1f".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
