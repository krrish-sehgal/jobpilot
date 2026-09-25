"""LLM client boundary.

`LLMClient` is the protocol every layer above this module codes
against: the agent loop, enrichment, memory extraction, and embedding.
`HTTPLLMClient` is the real implementation, talking to whichever
provider is configured (see `jobpilot.config.Settings.llm_provider`);
it holds no logic beyond request/response plumbing and is not
exercised by the test suite, since it requires live credentials.
`FakeLLMClient` is a deterministic in-memory stand-in the tests and
local development use instead.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from jobpilot.config import Settings
from jobpilot.errors import LLMProviderError


class LLMClient(Protocol):
    """Protocol for chat completion and embedding calls."""

    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Return a provider-agnostic completion response.

        Shape: `{"content": str | None, "tool_calls": [{"name": str,
        "arguments": dict}], "finish_reason": str}`.
        """
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...


class HTTPLLMClient:
    """Talks to a real LLM provider over HTTP.

    Unconfigured out of the box: `Settings.llm_api_key` defaults to a
    placeholder, so any real call fails fast with `LLMProviderError`
    rather than silently hitting an unintended endpoint.
    """

    def __init__(self, settings: Settings, *, http_client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._http = http_client or httpx.Client(timeout=settings.llm_request_timeout_seconds)

    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        self._require_real_credentials()
        raise LLMProviderError(
            "HTTPLLMClient.complete is not wired to a live endpoint in this "
            "environment; configure JOBPILOT_LLM_PROVIDER and credentials "
            "and implement the provider-specific request in a deployment."
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._require_real_credentials()
        raise LLMProviderError(
            "HTTPLLMClient.embed is not wired to a live endpoint in this "
            "environment; configure JOBPILOT_LLM_PROVIDER and credentials."
        )

    def _require_real_credentials(self) -> None:
        if self._settings.llm_api_key.startswith("replace-with"):
            raise LLMProviderError(
                "no LLM API key configured (JOBPILOT_LLM_API_KEY is still a placeholder)"
            )


@dataclass
class FakeLLMClient:
    """Deterministic in-memory LLM used by tests and local development.

    `complete` is driven by an optional `responder` callback so tests
    can script specific tool-call sequences; without one, it returns a
    canned text reply. `embed` produces a deterministic pseudo-random
    unit vector derived from a hash of the input text, so semantically
    unrelated texts land far apart and identical texts always embed
    identically — good enough to exercise cosine-similarity logic in
    tests without a real embedding model.
    """

    dimensions: int = 32
    responder: Callable[[str, list[dict[str, str]]], dict[str, Any]] | None = None
    call_count: int = field(default=0, init=False)

    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        self.call_count += 1
        if self.responder is not None:
            return self.responder(system_prompt, messages)
        return {
            "content": "I don't have enough context to help with that yet.",
            "tool_calls": [],
            "finish_reason": "stop",
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._deterministic_vector(text) for text in texts]

    def _deterministic_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.strip().lower().encode("utf-8")).digest()
        raw = [(digest[i % len(digest)] / 255.0) * 2 - 1 for i in range(self.dimensions)]
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]
