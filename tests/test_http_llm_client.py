import json

import httpx
import pytest

from jobpilot.config import Settings
from jobpilot.errors import LLMProviderError
from jobpilot.integrations.llm import HTTPLLMClient

SETTINGS = Settings(
    llm_api_key="sk-test",
    llm_base_url="https://llm.test/v1/",
    llm_chat_model="chat-model",
    llm_embedding_model="embed-model",
    llm_embedding_dimensions=8,
    retry_max_attempts=3,
)
TOOL = {
    "name": "search_jobs",
    "description": "Search postings.",
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
}


def make_client(handler, settings: Settings = SETTINGS) -> HTTPLLMClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return HTTPLLMClient(settings, http_client=http, sleep=lambda _s: None)


def test_complete_sends_openai_style_request_and_parses_tool_calls():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_jobs",
                                        "arguments": '{"query": "remote python"}',
                                    },
                                }
                            ],
                        },
                    }
                ]
            },
        )

    result = make_client(handler).complete(
        system_prompt="be brief",
        messages=[{"role": "user", "content": "find jobs"}],
        tools=[TOOL],
        temperature=0.0,
    )

    assert result == {
        "content": None,
        "tool_calls": [{"name": "search_jobs", "arguments": {"query": "remote python"}}],
        "finish_reason": "tool_calls",
    }
    request = seen[0]
    assert str(request.url) == "https://llm.test/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer sk-test"
    body = json.loads(request.content)
    assert body["model"] == "chat-model" and body["temperature"] == 0.0
    assert body["messages"][0] == {"role": "system", "content": "be brief"}
    assert body["messages"][1] == {"role": "user", "content": "find jobs"}
    assert body["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "search_jobs",
                "description": "Search postings.",
                "parameters": TOOL["input_schema"],
            },
        }
    ]


def test_complete_without_tools_omits_the_tools_field_and_returns_text():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "tools" not in json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": "hello"}}]},
        )

    result = make_client(handler).complete(system_prompt="s", messages=[])
    assert result == {"content": "hello", "tool_calls": [], "finish_reason": "stop"}


def test_embed_returns_vectors_in_input_order():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        body = json.loads(request.content)
        assert body["input"] == ["a", "b"] and body["dimensions"] == 8
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0, 0, 1]},
                    {"index": 0, "embedding": [1, 0, 0]},
                ]
            },
        )

    assert make_client(handler).embed(["a", "b"]) == [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]


def test_transient_failures_are_retried_then_succeed():
    statuses = iter([429, 503])

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses, 200)
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2, 3]}]})

    assert make_client(handler).embed(["a"]) == [[1.0, 2.0, 3.0]]


def test_persistent_server_errors_raise_provider_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500)

    with pytest.raises(LLMProviderError):
        make_client(handler).embed(["a"])
    assert len(calls) == SETTINGS.retry_max_attempts


def test_client_errors_are_not_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(401, text="bad key")

    with pytest.raises(LLMProviderError, match="401"):
        make_client(handler).complete(system_prompt="s", messages=[])
    assert len(calls) == 1


def test_malformed_tool_arguments_raise_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        call = {"function": {"name": "search_jobs", "arguments": "{not json"}}
        message = {"content": None, "tool_calls": [call]}
        return httpx.Response(200, json={"choices": [{"message": message}]})

    with pytest.raises(LLMProviderError, match="not valid JSON"):
        make_client(handler).complete(system_prompt="s", messages=[])


def test_placeholder_api_key_fails_before_any_request():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request expected")

    with pytest.raises(LLMProviderError, match="API key"):
        make_client(handler, Settings()).embed(["a"])
