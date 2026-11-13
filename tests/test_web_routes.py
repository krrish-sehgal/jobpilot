from __future__ import annotations

import pytest

from tests.web_fixtures import API, ORIGIN, assert_error

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
    assert 0 <= body["match_score"] <= 100 and body["posted_at"].endswith("Z")


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
