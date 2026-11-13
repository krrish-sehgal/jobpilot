"""LLM client boundary.

`LLMClient` is the protocol every layer above this module codes
against: the agent loop, enrichment, memory extraction, and embedding.
`HTTPLLMClient` is the production implementation for any
OpenAI-compatible provider (base URL, key and models come from
`jobpilot.config.Settings`); it holds no logic beyond request/response
mapping. `FakeLLMClient` is a deterministic in-memory test double for
tests and local development.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from jobpilot.config import Settings
from jobpilot.errors import LLMProviderError
from jobpilot.utils.retry import RetryExhaustedError, retry_call


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


class _RetryableStatusError(Exception):
    """Internal: a 429/5xx or transport failure that is worth retrying."""


def _to_function_tool(schema: dict[str, Any]) -> dict[str, Any]:
    """Map a registry tool schema to the function-calling `tools` format."""

    return {
        "type": "function",
        "function": {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": schema.get("input_schema", {"type": "object", "properties": {}}),
        },
    }


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise LLMProviderError(f"tool call arguments were not valid JSON: {raw!r}") from exc
    if not isinstance(parsed, dict):
        raise LLMProviderError("tool call arguments must be a JSON object")
    return parsed


class HTTPLLMClient:
    """Client for any OpenAI-compatible provider (`/chat/completions`, `/embeddings`).

    Requests go to `Settings.llm_base_url`. 429 and 5xx responses and
    transport errors are retried with jittered backoff; any other
    failure is raised as `LLMProviderError`.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._http = http_client or httpx.Client(timeout=settings.llm_request_timeout_seconds)
        self._sleep = sleep

    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._settings.llm_chat_model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = [_to_function_tool(t) for t in tools]
        body = self._post("/chat/completions", payload)
        try:
            choice = body["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("unexpected chat completion response shape") from exc
        tool_calls = [
            {
                "name": call["function"]["name"],
                "arguments": _parse_arguments(call["function"].get("arguments")),
            }
            for call in message.get("tool_calls") or []
        ]
        return {
            "content": message.get("content"),
            "tool_calls": tool_calls,
            "finish_reason": choice.get("finish_reason") or "stop",
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        body = self._post(
            "/embeddings",
            {
                "model": self._settings.llm_embedding_model,
                "input": texts,
                "dimensions": self._settings.llm_embedding_dimensions,
            },
        )
        try:
            rows = sorted(body["data"], key=lambda row: row["index"])
            vectors = [[float(x) for x in row["embedding"]] for row in rows]
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMProviderError("unexpected embeddings response shape") from exc
        if len(vectors) != len(texts):
            raise LLMProviderError(
                f"expected {len(texts)} embeddings, provider returned {len(vectors)}"
            )
        return vectors

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._settings.llm_api_key.startswith("replace-with"):
            raise LLMProviderError(
                "no LLM API key configured (JOBPILOT_LLM_API_KEY is still a placeholder)"
            )
        url = self._settings.llm_base_url.rstrip("/") + path
        headers = {"Authorization": f"Bearer {self._settings.llm_api_key}"}

        def attempt() -> httpx.Response:
            try:
                response = self._http.post(url, json=payload, headers=headers)
            except httpx.TransportError as exc:
                raise _RetryableStatusError(f"transport error: {exc}") from exc
            if response.status_code == 429 or response.status_code >= 500:
                raise _RetryableStatusError(f"provider returned HTTP {response.status_code}")
            return response

        try:
            response = retry_call(
                attempt,
                max_attempts=self._settings.retry_max_attempts,
                base_delay_seconds=self._settings.retry_base_delay_seconds,
                max_delay_seconds=self._settings.retry_max_delay_seconds,
                retry_on=(_RetryableStatusError,),
                sleep=self._sleep,
            )
        except RetryExhaustedError as exc:
            raise LLMProviderError(f"LLM request to {path} failed: {exc.last_exception}") from exc
        if response.status_code >= 400:
            raise LLMProviderError(
                f"LLM request to {path} failed with HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise LLMProviderError(f"LLM response from {path} was not valid JSON") from exc


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
