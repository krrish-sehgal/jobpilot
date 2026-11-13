"""Chat over HTTP: posting, idempotency, streaming, replay, and agent-started tailoring."""

from __future__ import annotations

from tests.web_fixtures import (
    API,
    FINAL_REPLY,
    ChatScript,
    assert_error,
    build_web,
    new_conversation,
    post_message,
    stream,
    upload,
)

# --- chat -----------------------------------------------------------------------


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


def test_a_failing_turn_streams_a_retryable_error():
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


# --- chat starts a tailoring --------------------------------------------------------


def test_agent_can_start_a_tailoring_from_chat():
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


def test_tailor_tool_without_a_resume_is_reported_not_started():
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
