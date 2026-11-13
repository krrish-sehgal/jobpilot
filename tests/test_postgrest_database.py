import json

import httpx
import pytest

from jobpilot.config import Settings
from jobpilot.errors import RecordNotFoundError, RepositoryError
from jobpilot.integrations.supabase_client import SupabaseDatabase

SETTINGS = Settings(
    supabase_url="https://abc.supabase.co/",
    supabase_service_role_key="service-key",
    retry_max_attempts=2,
)


def make_db(handler, settings: Settings = SETTINGS) -> SupabaseDatabase:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return SupabaseDatabase(settings, http_client=http, sleep=lambda _s: None)


def test_insert_upserts_with_auth_headers_and_returns_the_stored_row():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json=[json.loads(request.content)])

    stored = make_db(handler).insert("jobs", {"id": "j1", "title": "Engineer"})

    assert stored == {"id": "j1", "title": "Engineer"}
    request = seen[0]
    assert request.method == "POST"
    assert request.url.path == "/rest/v1/jobs"
    assert request.url.params["on_conflict"] == "id"
    assert request.headers["apikey"] == "service-key"
    assert request.headers["authorization"] == "Bearer service-key"
    assert "return=representation" in request.headers["prefer"]
    assert "merge-duplicates" in request.headers["prefer"]


def test_insert_generates_an_id_when_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=[json.loads(request.content)])

    assert make_db(handler).insert("jobs", {"title": "x"})["id"]


def test_get_filters_by_id_and_raises_when_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["id"] == "eq.j1"
        return httpx.Response(200, json=[])

    with pytest.raises(RecordNotFoundError):
        make_db(handler).get("jobs", "j1")


def test_find_builds_equality_filters():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[{"id": "m1"}])

    rows = make_db(handler).find("messages", conversation_id="c1", read=False, deleted_at=None)

    assert rows == [{"id": "m1"}]
    params = seen[0].url.params
    assert params["conversation_id"] == "eq.c1"
    assert params["read"] == "eq.false"
    assert params["deleted_at"] == "is.null"


def test_find_pages_through_large_result_sets():
    offsets = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        size = 1000 if offset == 0 else 3
        return httpx.Response(200, json=[{"id": str(offset + i)} for i in range(size)])

    assert len(make_db(handler).find("jobs")) == 1003
    assert offsets == [0, 1000]


def test_update_patches_by_id_and_delete_removes_by_id():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "PATCH":
            return httpx.Response(200, json=[{"id": "j1", "title": "New"}])
        return httpx.Response(204)

    db = make_db(handler)
    assert db.update("jobs", "j1", {"title": "New"}) == {"id": "j1", "title": "New"}
    db.delete("jobs", "j1")
    assert [r.method for r in seen] == ["PATCH", "DELETE"]
    assert json.loads(seen[0].content) == {"title": "New"}
    assert all(r.url.params["id"] == "eq.j1" for r in seen)


def test_update_of_a_missing_row_raises_not_found():
    with pytest.raises(RecordNotFoundError):
        make_db(lambda request: httpx.Response(200, json=[])).update("jobs", "nope", {"a": 1})


def test_transient_errors_are_retried_and_client_errors_are_not():
    attempts = []

    def flaky(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(503) if len(attempts) == 1 else httpx.Response(200, json=[])

    assert make_db(flaky).find("jobs") == []
    assert len(attempts) == 2

    with pytest.raises(RepositoryError, match="400"):
        make_db(lambda request: httpx.Response(400, text="bad")).find("jobs")


def test_placeholder_project_url_fails_before_any_request():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request expected")

    with pytest.raises(RepositoryError, match="no Supabase project"):
        make_db(handler, Settings()).find("jobs")
