"""Resume upload and tailoring over HTTP."""

from __future__ import annotations

from tests.resume_fixtures import make_docx, make_pdf
from tests.web_fixtures import API, assert_error, start_tailoring, upload

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
