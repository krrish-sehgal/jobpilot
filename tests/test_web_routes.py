"""Route tests against the in-memory fakes. One class of behaviour per test."""

from __future__ import annotations

import pytest

from tests.resume_fixtures import make_docx, make_pdf
from tests.web_fixtures import FINAL_REPLY, ORIGIN, ChatScript, Web, build_web, parse_sse

API = "/api/v1"


@pytest.fixture
def web() -> Web:
    return build_web()


@pytest.fixture
def auth(web: Web) -> dict[str, str]:
    return web.sign_in()


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


# --- auth, errors, CORS -------------------------------------------------------


def test_healthz_needs_no_token(web):
    assert web.client.get(f"{API}/healthz").json() == {"status": "ok"}


def test_sign_in_flow_and_me(web):
    sent = web.client.post(f"{API}/auth/request-code", json={"email": "Ada@example.com"})
    assert (sent.status_code, sent.json()) == (202, {"sent": True})
    verified = web.client.post(
        f"{API}/auth/verify-code",
        json={"email": "ada@example.com", "code": web.sender.codes["ada@example.com"]},
    )
    assert verified.status_code == 200
    body = verified.json()
    assert set(body) == {"access_token", "expires_at", "user"}
    assert set(body["user"]) == {
        "id", "email", "full_name", "seniority_band", "preferred_location_tiers",
        "has_resume", "created_at",
    }  # fmt: skip
    me = web.client.get(f"{API}/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json() == body["user"] and me.json()["has_resume"] is False


def test_wrong_code_and_lockout(web):
    web.client.post(f"{API}/auth/request-code", json={"email": "ada@example.com"})
    good = web.sender.codes["ada@example.com"]
    bad = "000000" if good != "000000" else "111111"
    for _ in range(4):
        r = web.client.post(
            f"{API}/auth/verify-code", json={"email": "ada@example.com", "code": bad}
        )
        assert_error(r, 401, "unauthorized")
    r = web.client.post(f"{API}/auth/verify-code", json={"email": "ada@example.com", "code": bad})
    assert_error(r, 429, "rate_limited")
    r = web.client.post(f"{API}/auth/verify-code", json={"email": "ada@example.com", "code": good})
    assert_error(r, 429, "rate_limited")


def test_invalid_email_and_body_are_validation_failed(web):
    assert_error(
        web.client.post(f"{API}/auth/request-code", json={"email": "nope"}),
        422,
        "validation_failed",
    )
    assert_error(web.client.post(f"{API}/auth/request-code", json={}), 422, "validation_failed")


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer garbage"},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer "},
    ],
)
def test_protected_routes_reject_missing_or_bad_tokens(web, headers):
    for path in ("/me", "/conversations", "/saved-jobs", "/resumes"):
        assert_error(web.client.get(f"{API}{path}", headers=headers), 401, "unauthorized")


def test_unknown_route_uses_the_error_shape(web):
    assert_error(web.client.get(f"{API}/nope"), 404, "not_found")


def test_cors_allows_only_configured_origins(web):
    allowed = web.client.options(
        f"{API}/me",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET",
                 "Access-Control-Request-Headers": "authorization"},
    )  # fmt: skip
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    denied = web.client.options(
        f"{API}/me",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in denied.headers


# --- chat -----------------------------------------------------------------------


def new_conversation(web, auth) -> str:
    response = web.client.post(f"{API}/conversations", json={}, headers=auth)
    assert response.status_code == 201
    assert set(response.json()) == {"id", "title", "last_message_preview", "updated_at"}
    return response.json()["id"]


def post_message(web, auth, conversation_id, body="find me remote backend roles", cmid=None):
    cmid = cmid or "7b0c3f9e-6f7a-4d6a-9f0e-1c2d3e4f5a6b"
    return web.client.post(
        f"{API}/conversations/{conversation_id}/messages",
        headers=auth,
        json={"body": body, "client_message_id": cmid},
    )


def stream(web, auth, conversation_id, turn_id):
    response = web.client.get(
        f"{API}/conversations/{conversation_id}/turns/{turn_id}/stream", headers=auth
    )
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_sse(response.text)


def test_posting_a_message_persists_it_and_returns_ids(web, auth):
    web.add_job()
    cid = new_conversation(web, auth)
    response = post_message(web, auth, cid)
    assert response.status_code == 202 and set(response.json()) == {"message_id", "turn_id"}
    history = web.client.get(f"{API}/conversations/{cid}/messages", headers=auth).json()
    assert [(m["role"], m["body"]) for m in history] == [("user", "find me remote backend roles")]
    listed = web.client.get(f"{API}/conversations", headers=auth).json()
    assert listed[0]["title"] == "find me remote backend roles"  # titled from the first message
    assert listed[0]["last_message_preview"] == "find me remote backend roles"


def test_same_client_message_id_returns_the_original_and_creates_one_turn(web, auth):
    cid = new_conversation(web, auth)
    first = post_message(web, auth, cid).json()
    again = post_message(web, auth, cid).json()
    assert again == first
    other = post_message(web, auth, cid, cmid="11111111-2222-4333-8444-555555555555").json()
    assert other["message_id"] != first["message_id"]
    history = web.client.get(f"{API}/conversations/{cid}/messages", headers=auth).json()
    assert len(history) == 2


def test_client_message_id_must_be_a_uuid_and_body_non_blank(web, auth):
    cid = new_conversation(web, auth)
    assert_error(post_message(web, auth, cid, cmid="not-a-uuid"), 422, "validation_failed")
    assert_error(post_message(web, auth, cid, body="   "), 422, "validation_failed")


def test_streamed_turn_emits_the_contract_events_in_order(web, auth):
    job = web.add_job(title="Senior Backend Engineer")
    cid = new_conversation(web, auth)
    ids = post_message(web, auth, cid).json()
    events = stream(web, auth, cid, ids["turn_id"])
    names = [name for name, _ in events]

    assert names[0] == "status" and events[0][1] == {"phase": "thinking"}
    assert names[-1] == "done"
    assert names.index("tool_call") < names.index("tool_result") < names.index("token")
    assert names.index("token") < names.index("job_cards") < names.index("done")

    call = dict(events)["tool_call"]
    result = dict(events)["tool_result"]
    assert call["name"] == "search_jobs" and call["label"] == "Searching remote backend roles"
    assert result["call_id"] == call["call_id"] and result["ok"] is True
    assert result["summary"] == "Found 1 matching role"
    assert {"phase": "calling_tool"} in [d for n, d in events if n == "status"]
    assert {"phase": "writing"} in [d for n, d in events if n == "status"]

    assert "".join(d["text"] for n, d in events if n == "token") == FINAL_REPLY
    cards = dict(events)["job_cards"]["cards"]
    assert cards[0]["job_id"] == str(job.id) and cards[0]["is_saved"] is False
    assert cards[0]["match_reasons"] and cards[0]["location_tier"] == "remote"

    history = web.client.get(f"{API}/conversations/{cid}/messages", headers=auth).json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[1]["id"] == dict(events)["done"]["message_id"]
    assert history[1]["body"] == FINAL_REPLY and history[1]["job_cards"][0]["job_id"] == str(job.id)
    assert history[1]["tailoring_id"] is None


def test_reconnecting_replays_the_stored_reply_without_running_the_agent_again(web, auth):
    web.add_job()
    cid = new_conversation(web, auth)
    ids = post_message(web, auth, cid).json()
    first = stream(web, auth, cid, ids["turn_id"])
    calls_after_first = web.container.llm.call_count
    replay = stream(web, auth, cid, ids["turn_id"])

    assert web.container.llm.call_count == calls_after_first  # no new model calls
    assert dict(replay)["done"] == dict(first)["done"]
    assert "".join(d["text"] for n, d in replay if n == "token") == FINAL_REPLY
    assert "job_cards" in dict(replay)
    history = web.client.get(f"{API}/conversations/{cid}/messages", headers=auth).json()
    assert len(history) == 2  # still one reply


def test_saved_state_of_old_cards_is_refreshed_on_read(web, auth):
    job = web.add_job()
    cid = new_conversation(web, auth)
    ids = post_message(web, auth, cid).json()
    stream(web, auth, cid, ids["turn_id"])
    web.client.post(f"{API}/jobs/{job.id}/save", headers=auth)
    history = web.client.get(f"{API}/conversations/{cid}/messages", headers=auth).json()
    assert history[1]["job_cards"][0]["is_saved"] is True


def test_a_failing_turn_streams_a_retryable_error(auth_web=None):
    web = build_web(ChatScript(fail=True))
    auth = web.sign_in()
    cid = new_conversation(web, auth)
    ids = post_message(web, auth, cid).json()
    events = stream(web, auth, cid, ids["turn_id"])
    assert events[-1][0] == "error"
    assert events[-1][1] == {
        "code": "turn_failed",
        "message": "something went wrong, please try again",
        "retryable": True,
    }
    assert "model exploded" not in str(events)  # internals do not leak
    history = web.client.get(f"{API}/conversations/{cid}/messages", headers=auth).json()
    assert [m["role"] for m in history] == ["user"]


def test_conversations_are_private_and_ids_are_checked(web, auth):
    cid = new_conversation(web, auth)
    ids = post_message(web, auth, cid).json()
    stranger = web.sign_in("mallory@example.com")
    assert_error(
        web.client.get(f"{API}/conversations/{cid}/messages", headers=stranger), 404, "not_found"
    )
    assert_error(post_message(web, stranger, cid), 404, "not_found")
    assert_error(
        web.client.get(
            f"{API}/conversations/{cid}/turns/{ids['turn_id']}/stream", headers=stranger
        ),
        404,
        "not_found",
    )
    assert web.client.get(f"{API}/conversations", headers=stranger).json() == []
    assert_error(
        web.client.get(f"{API}/conversations/{cid}/turns/{cid}/stream", headers=auth),
        404,
        "not_found",
    )
    assert_error(
        web.client.get(f"{API}/conversations/nope/messages", headers=auth), 404, "not_found"
    )


# --- jobs -----------------------------------------------------------------------


def test_job_detail_has_card_and_detail_fields(web, auth):
    job = web.add_job()
    body = web.client.get(f"{API}/jobs/{job.id}", headers=auth).json()
    assert {
        "job_id", "title", "company", "location_text", "location_tier", "seniority_band",
        "role_category", "skills", "description_preview", "compensation_text", "apply_url",
        "match_score", "match_reasons", "posted_at", "is_saved", "description",
        "employment_type", "min_years_experience",
    } == set(body)  # fmt: skip
    assert body["job_id"] == str(job.id) and body["employment_type"] == "full_time"
    assert 0 <= body["match_score"] <= 1 and body["posted_at"].endswith("Z")


def test_save_and_unsave_are_idempotent_and_listed(web, auth):
    job = web.add_job()
    other = web.add_job(title="Data Engineer")
    for _ in range(2):
        assert web.client.post(f"{API}/jobs/{job.id}/save", headers=auth).status_code == 204
    web.client.post(f"{API}/jobs/{other.id}/save", headers=auth)
    saved = web.client.get(f"{API}/saved-jobs", headers=auth).json()
    assert [c["job_id"] for c in saved] == [str(other.id), str(job.id)]
    assert all(c["is_saved"] for c in saved)
    for _ in range(2):
        assert web.client.delete(f"{API}/jobs/{job.id}/save", headers=auth).status_code == 204
    assert [c["job_id"] for c in web.client.get(f"{API}/saved-jobs", headers=auth).json()] == [
        str(other.id)
    ]
    assert web.client.get(f"{API}/jobs/{job.id}", headers=auth).json()["is_saved"] is False


def test_unknown_jobs_are_not_found(web, auth):
    unknown = "00000000-0000-4000-8000-000000000000"
    assert_error(web.client.get(f"{API}/jobs/{unknown}", headers=auth), 404, "not_found")
    assert_error(web.client.post(f"{API}/jobs/{unknown}/save", headers=auth), 404, "not_found")
    assert_error(web.client.get(f"{API}/jobs/not-a-uuid", headers=auth), 404, "not_found")


# --- resumes ----------------------------------------------------------------------


def test_upload_parse_list_and_get(web, auth):
    response = web.client.post(
        f"{API}/resumes", headers=auth, files={"file": ("my cv.pdf", make_pdf())}
    )
    assert response.status_code == 202
    assert response.json()["status"] == "parsing"  # the contract's immediate answer
    resume_id = response.json()["resume_id"]

    listed = web.client.get(f"{API}/resumes", headers=auth).json()
    assert listed == [
        {"id": resume_id, "file_name": "my cv.pdf", "status": "ready", "is_primary": True,
         "uploaded_at": listed[0]["uploaded_at"]}
    ]  # fmt: skip
    resume = web.client.get(f"{API}/resumes/{resume_id}", headers=auth).json()
    assert resume["failure_reason"] is None
    assert resume["sections"]["contact"]["name"] == "Priya Nair"
    assert resume["sections"]["experience"][0]["bullets"][0]["id"]

    me = web.client.get(f"{API}/me", headers=auth).json()
    assert me["has_resume"] is True and me["full_name"] == "Priya Nair"
    assert me["seniority_band"] == "senior"  # inferred from the resume's dates


def test_upload_validation_errors(web, auth):
    r = web.client.post(f"{API}/resumes", headers=auth, files={"file": ("cv.pdf", b"plain text")})
    assert_error(r, 415, "unsupported_file_type")
    r = web.client.post(
        f"{API}/resumes",
        headers=auth,
        files={"file": ("cv.pdf", make_pdf("x" * (5 * 1024 * 1024)))},
    )
    assert_error(r, 413, "file_too_large")
    assert_error(web.client.post(f"{API}/resumes", headers=auth), 422, "validation_failed")


def test_primary_switching_and_ownership(web, auth):
    first = upload(web, auth)
    second = upload(web, auth, data=make_docx(), name="cv.docx")
    assert web.client.post(f"{API}/resumes/{second}/primary", headers=auth).status_code == 204
    primary = {
        r["id"]: r["is_primary"] for r in web.client.get(f"{API}/resumes", headers=auth).json()
    }
    assert primary == {first: False, second: True}
    stranger = web.sign_in("mallory@example.com")
    assert_error(web.client.get(f"{API}/resumes/{first}", headers=stranger), 404, "not_found")
    assert_error(
        web.client.post(f"{API}/resumes/{first}/primary", headers=stranger), 404, "not_found"
    )


def test_failed_parse_is_reported_and_cannot_be_primary(web, auth):
    upload(web, auth)
    web.container.llm.responder = lambda s, m: {"content": "not json", "tool_calls": []}
    bad = upload(web, auth)
    resume = web.client.get(f"{API}/resumes/{bad}", headers=auth).json()
    assert resume["status"] == "failed" and resume["failure_reason"] and resume["sections"] is None
    assert_error(
        web.client.post(f"{API}/resumes/{bad}/primary", headers=auth), 409, "resume_not_ready"
    )


# --- tailoring ---------------------------------------------------------------------


def start_tailoring(web, auth, **payload):
    resume_id = payload.pop("resume_id", None) or upload(web, auth)
    response = web.client.post(
        f"{API}/tailorings", headers=auth, json={"resume_id": resume_id, **payload}
    )
    return resume_id, response


def test_tailoring_lifecycle_for_a_job(web, auth):
    job = web.add_job(skills=["python", "jenkins"])
    resume_id, response = start_tailoring(web, auth, job_id=str(job.id))
    assert response.status_code == 202
    assert response.json()["status"] == "running" and set(response.json()) == {
        "tailoring_id",
        "status",
    }

    tailoring = web.client.get(
        f"{API}/tailorings/{response.json()['tailoring_id']}", headers=auth
    ).json()
    assert set(tailoring) == {
        "id", "resume_id", "job_id", "job_title", "company", "status", "score_before",
        "score_after", "keywords", "suggestions", "created_at",
    }  # fmt: skip
    assert tailoring["status"] == "ready" and tailoring["resume_id"] == resume_id
    assert tailoring["job_title"] == job.title and tailoring["company"] == job.company
    assert tailoring["score_after"] > tailoring["score_before"]
    assert set(tailoring["keywords"][0]) == {
        "term",
        "importance",
        "found_in_resume",
        "covered_after",
    }
    suggestion = tailoring["suggestions"][0]
    assert set(suggestion) == {
        "id", "kind", "target_id", "section", "original", "proposed", "reason",
        "keywords_added", "decision",
    }  # fmt: skip
    assert suggestion["decision"] == "pending" and suggestion["proposed"] == "Jenkins"

    decided = web.client.post(
        f"{API}/tailorings/{tailoring['id']}/decisions",
        headers=auth,
        json={"accepted": [suggestion["id"]], "rejected": []},
    )
    assert decided.status_code == 200
    assert decided.json()["suggestions"][0]["decision"] == "accepted"

    pdf = web.client.get(f"{API}/tailorings/{tailoring['id']}/export?format=pdf", headers=auth)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert "priya-nair-tailored.pdf" in pdf.headers["content-disposition"]
    assert b"Jenkins" in pdf.content.split(b"SKILLS")[-1]
    docx = web.client.get(f"{API}/tailorings/{tailoring['id']}/export?format=docx", headers=auth)
    assert docx.headers["content-type"].endswith("wordprocessingml.document")
    assert docx.content[:2] == b"PK"


def test_tailoring_from_pasted_description(web, auth):
    _, response = start_tailoring(web, auth, job_description_text="We need Python and Jenkins.")
    assert response.status_code == 202
    tailoring = web.client.get(
        f"{API}/tailorings/{response.json()['tailoring_id']}", headers=auth
    ).json()
    assert tailoring["status"] == "ready" and tailoring["job_id"] is None
    assert tailoring["job_title"] == "Pasted job description"


def test_tailoring_request_validation(web, auth):
    job = web.add_job()
    resume_id = upload(web, auth)
    for payload in (
        {"resume_id": resume_id},
        {"resume_id": resume_id, "job_id": str(job.id), "job_description_text": "x"},
        {"resume_id": resume_id, "job_description_text": "   "},
        {"resume_id": "not-a-uuid", "job_id": str(job.id)},
    ):
        r = web.client.post(f"{API}/tailorings", headers=auth, json=payload)
        assert_error(r, 422, "validation_failed")
    unknown = "00000000-0000-4000-8000-000000000000"
    r = web.client.post(
        f"{API}/tailorings", headers=auth, json={"resume_id": resume_id, "job_id": unknown}
    )
    assert_error(r, 404, "not_found")


def test_decisions_and_export_validation(web, auth):
    job = web.add_job(skills=["python", "jenkins"])
    _, response = start_tailoring(web, auth, job_id=str(job.id))
    tid = response.json()["tailoring_id"]
    sid = web.client.get(f"{API}/tailorings/{tid}", headers=auth).json()["suggestions"][0]["id"]

    unknown = "00000000-0000-4000-8000-000000000000"
    for payload in (
        {"accepted": [unknown], "rejected": []},
        {"accepted": [sid], "rejected": [sid]},
        {"accepted": ["nope"], "rejected": []},
    ):
        assert_error(
            web.client.post(f"{API}/tailorings/{tid}/decisions", headers=auth, json=payload),
            422,
            "validation_failed",
        )
    assert_error(
        web.client.get(f"{API}/tailorings/{tid}/export?format=txt", headers=auth),
        422,
        "validation_failed",
    )
    assert_error(
        web.client.get(f"{API}/tailorings/{tid}/export", headers=auth), 422, "validation_failed"
    )


def test_tailorings_are_private(web, auth):
    job = web.add_job()
    _, response = start_tailoring(web, auth, job_id=str(job.id))
    tid = response.json()["tailoring_id"]
    stranger = web.sign_in("mallory@example.com")
    assert_error(web.client.get(f"{API}/tailorings/{tid}", headers=stranger), 404, "not_found")
    assert_error(
        web.client.post(f"{API}/tailorings/{tid}/decisions", headers=stranger, json={}),
        404,
        "not_found",
    )
    assert_error(
        web.client.get(f"{API}/tailorings/{tid}/export?format=pdf", headers=stranger),
        404,
        "not_found",
    )
    r = web.client.post(
        f"{API}/tailorings", headers=stranger,
        json={"resume_id": upload(web, auth), "job_id": str(job.id)},
    )  # fmt: skip
    assert_error(r, 404, "not_found")


# --- chat starts a tailoring --------------------------------------------------------


def test_agent_can_start_a_tailoring_from_chat(auth_web=None):
    web = build_web()
    auth = web.sign_in()
    job = web.add_job(skills=["python", "jenkins"])
    upload(web, auth)
    web.script.tool = {"name": "tailor_resume", "arguments": {"job_id": str(job.id)}}
    cid = new_conversation(web, auth)
    ids = post_message(web, auth, cid, body="tailor my resume for that role").json()

    events = stream(web, auth, cid, ids["turn_id"])
    names = [n for n, _ in events]
    assert names.index("tool_result") < names.index("tailoring_started") < names.index("done")
    started = dict(events)["tailoring_started"]
    assert started["job_id"] == str(job.id)
    assert dict(events)["tool_result"]["summary"] == f"Started tailoring for {job.title}"

    history = web.client.get(f"{API}/conversations/{cid}/messages", headers=auth).json()
    assert history[-1]["tailoring_id"] == started["tailoring_id"]
    tailoring = web.client.get(f"{API}/tailorings/{started['tailoring_id']}", headers=auth).json()
    assert tailoring["status"] == "ready" and tailoring["job_id"] == str(job.id)


def test_tailor_tool_without_a_resume_is_reported_not_started(auth_web=None):
    web = build_web()
    auth = web.sign_in()
    job = web.add_job()
    web.script.tool = {"name": "tailor_resume", "arguments": {"job_id": str(job.id)}}
    cid = new_conversation(web, auth)
    ids = post_message(web, auth, cid).json()
    events = stream(web, auth, cid, ids["turn_id"])
    assert "tailoring_started" not in dict(events)
    result = dict(events)["tool_result"]
    assert result["ok"] is False and result["summary"] == "You have not uploaded a resume yet"
