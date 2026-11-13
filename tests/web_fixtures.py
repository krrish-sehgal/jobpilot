"""A fully wired web app over the in-memory fakes, for route tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from jobpilot.agent.prompts import AGENT_SYSTEM_PROMPT
from jobpilot.config import Settings
from jobpilot.integrations.llm import FakeLLMClient
from jobpilot.integrations.storage import InMemoryObjectStorage
from jobpilot.integrations.supabase_client import InMemoryDatabase
from jobpilot.models import JobRecord
from jobpilot.resume.prompts import (
    KEYWORD_SYSTEM_PROMPT,
    PARSE_SYSTEM_PROMPT,
    TAILOR_SYSTEM_PROMPT,
)
from jobpilot.resume.service import run_inline
from jobpilot.web.app import create_web_app
from jobpilot.web.auth import RecordingCodeSender
from jobpilot.web.deps import WebContainer, build_container
from tests.conftest import make_job_record
from tests.doubles import PlainTextExtractor, PlainTextRenderer
from tests.resume_fixtures import make_pdf, sample_resume_json

ORIGIN = "https://app.example.com"
FINAL_REPLY = (
    "I found a strong remote backend role at Acme Corp that fits your Python background. "
    "Want me to tailor your resume for it?"
)
SKILL_SUGGESTION = {
    "kind": "add_skill",
    "section": "skills",
    "proposed": "Jenkins",
    "reason": "Required, and your CI work shows it.",
    "keywords_added": ["jenkins"],
}


@dataclass
class ChatScript:
    """What the fake model does on a chat turn: optionally one tool call, then a reply."""

    tool: dict | None = field(
        default_factory=lambda: {
            "name": "search_jobs",
            "arguments": {"query": "remote backend roles"},
        }
    )
    reply: str = FINAL_REPLY
    fail: bool = False


@dataclass
class Web:
    client: TestClient
    container: WebContainer
    sender: RecordingCodeSender
    script: ChatScript
    db: InMemoryDatabase

    def sign_in(self, email: str = "ada@example.com") -> dict[str, str]:
        self.client.post("/api/v1/auth/request-code", json={"email": email})
        code = self.sender.codes[email.strip().lower()]
        response = self.client.post("/api/v1/auth/verify-code", json={"email": email, "code": code})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def add_job(self, **kwargs) -> JobRecord:
        return self.container.jobs.save(make_job_record(**kwargs))


def build_web(script: ChatScript | None = None, *, suggestions: list[dict] | None = None) -> Web:
    script = script or ChatScript()
    resume_replies = {
        PARSE_SYSTEM_PROMPT: sample_resume_json(),
        KEYWORD_SYSTEM_PROMPT: json.dumps({"required": ["python", "jenkins"], "preferred": []}),
        TAILOR_SYSTEM_PROMPT: json.dumps({"suggestions": suggestions or [SKILL_SUGGESTION]}),
    }

    def responder(system_prompt: str, messages: list[dict]) -> dict:
        if system_prompt in resume_replies:
            return {"content": resume_replies[system_prompt], "tool_calls": []}
        assert system_prompt.startswith(AGENT_SYSTEM_PROMPT)
        if script.fail:
            raise RuntimeError("model exploded")
        if script.tool and len(messages) == 1:
            return {"content": None, "tool_calls": [script.tool], "finish_reason": "tool_use"}
        return {"content": script.reply, "tool_calls": [], "finish_reason": "stop"}

    db = InMemoryDatabase()
    sender = RecordingCodeSender()
    settings = Settings(
        environment="test",
        auth_token_secret="test-secret-with-enough-entropy",
        web_allowed_origins=f"http://localhost:3000, {ORIGIN}",
    )
    container = build_container(
        settings,
        db=db,
        llm=FakeLLMClient(responder=responder),
        storage=InMemoryObjectStorage(),
        code_sender=sender,
        extractor=PlainTextExtractor(),
        renderer=PlainTextRenderer(),
        scheduler=run_inline,
    )
    client = TestClient(create_web_app(settings, container=container))
    return Web(client=client, container=container, sender=sender, script=script, db=db)


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into `[(event, data), ...]`, ignoring comment frames."""

    events = []
    for frame in text.strip().split("\n\n"):
        lines = [line for line in frame.splitlines() if not line.startswith(":")]
        if not lines:
            continue
        name = next(line[7:] for line in lines if line.startswith("event: "))
        data = next(line[6:] for line in lines if line.startswith("data: "))
        events.append((name, json.loads(data)))
    return events


# --- shared route-test helpers ------------------------------------------------

API = "/api/v1"


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code


def upload(web: Web, auth, data=None, name="cv.pdf"):
    response = web.client.post(
        f"{API}/resumes", headers=auth, files={"file": (name, data or make_pdf())}
    )
    assert response.status_code == 202, response.text
    return response.json()["resume_id"]


def new_conversation(web: Web, auth) -> str:
    response = web.client.post(f"{API}/conversations", json={}, headers=auth)
    assert response.status_code == 201
    assert set(response.json()) == {"id", "title", "last_message_preview", "updated_at"}
    return response.json()["id"]


def post_message(web: Web, auth, conversation_id, body="find me remote backend roles", cmid=None):
    cmid = cmid or "7b0c3f9e-6f7a-4d6a-9f0e-1c2d3e4f5a6b"
    return web.client.post(
        f"{API}/conversations/{conversation_id}/messages",
        headers=auth,
        json={"body": body, "client_message_id": cmid},
    )


def stream(web: Web, auth, conversation_id, turn_id):
    response = web.client.get(
        f"{API}/conversations/{conversation_id}/turns/{turn_id}/stream", headers=auth
    )
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_sse(response.text)


def start_tailoring(web: Web, auth, **payload):
    resume_id = payload.pop("resume_id", None) or upload(web, auth)
    response = web.client.post(
        f"{API}/tailorings", headers=auth, json={"resume_id": resume_id, **payload}
    )
    return resume_id, response
