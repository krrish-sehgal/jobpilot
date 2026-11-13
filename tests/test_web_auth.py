"""Sign-in codes and access tokens."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from jobpilot.db.repositories.accounts import AuthCodeRepository, UserAccountRepository
from jobpilot.errors import (
    CodeExpiredError,
    InvalidCodeError,
    InvalidTokenError,
    RequestRejectedError,
    TooManyAttemptsError,
)
from jobpilot.integrations.supabase_client import InMemoryDatabase
from jobpilot.web.auth import (
    CODE_TTL,
    MAX_CODES_PER_WINDOW,
    MAX_VERIFY_ATTEMPTS,
    AuthService,
    RecordingCodeSender,
    TokenSigner,
    hash_code,
    normalize_email,
)

SECRET = "unit-test-secret"
EMAIL = "ada@example.com"
START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def setup(clock):
    db = InMemoryDatabase()
    sender = RecordingCodeSender()
    codes = AuthCodeRepository(db)
    signer = TokenSigner(SECRET, timedelta(hours=1), clock)
    service = AuthService(
        accounts=UserAccountRepository(db),
        codes=codes,
        signer=signer,
        sender=sender,
        secret=SECRET,
        clock=clock,
    )
    return service, sender, codes, signer


def wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


def test_code_roundtrip_returns_a_working_token(setup):
    service, sender, _, signer = setup
    service.request_code("  Ada@Example.COM ")
    token, expires_at, user = service.verify_code(EMAIL, sender.codes[EMAIL])
    assert user.email == EMAIL and signer.verify(token) == user.id
    assert expires_at == START + timedelta(hours=1)


def test_code_is_single_use(setup):
    service, sender, _, _ = setup
    service.request_code(EMAIL)
    code = sender.codes[EMAIL]
    service.verify_code(EMAIL, code)
    with pytest.raises(InvalidCodeError):
        service.verify_code(EMAIL, code)


def test_only_a_keyed_hash_is_stored(setup):
    service, sender, codes, _ = setup
    service.request_code(EMAIL)
    stored = codes.latest_active(EMAIL)
    code = sender.codes[EMAIL]
    assert len(code) == 6 and code.isdigit()
    assert code not in stored.code_hash
    assert stored.code_hash == hash_code(SECRET, EMAIL, code)
    assert hash_code("another-secret", EMAIL, code) != stored.code_hash
    assert hash_code(SECRET, "other@example.com", code) != stored.code_hash


def test_code_expires_after_ten_minutes(setup, clock):
    service, sender, _, _ = setup
    service.request_code(EMAIL)
    clock.advance(minutes=10)
    assert timedelta(minutes=10) == CODE_TTL
    with pytest.raises(CodeExpiredError):
        service.verify_code(EMAIL, sender.codes[EMAIL])


def test_code_still_works_just_before_expiry(setup, clock):
    service, sender, _, _ = setup
    service.request_code(EMAIL)
    clock.advance(minutes=9, seconds=59)
    service.verify_code(EMAIL, sender.codes[EMAIL])


def test_five_wrong_attempts_lock_the_code_even_for_the_right_answer(setup):
    service, sender, _, _ = setup
    service.request_code(EMAIL)
    good = sender.codes[EMAIL]
    for _ in range(MAX_VERIFY_ATTEMPTS - 1):
        with pytest.raises(InvalidCodeError):
            service.verify_code(EMAIL, wrong(good))
    with pytest.raises(TooManyAttemptsError):  # the 5th wrong guess trips the limit
        service.verify_code(EMAIL, wrong(good))
    with pytest.raises(TooManyAttemptsError):
        service.verify_code(EMAIL, good)

    service.request_code(EMAIL)  # a fresh code starts clean
    service.verify_code(EMAIL, sender.codes[EMAIL])


def test_new_code_supersedes_the_old_one(setup):
    service, sender, _, _ = setup
    service.request_code(EMAIL)
    first = sender.codes[EMAIL]
    service.request_code(EMAIL)
    second = sender.codes[EMAIL]
    if first != second:  # (1 in a million they collide)
        with pytest.raises(InvalidCodeError):
            service.verify_code(EMAIL, first)
    service.verify_code(EMAIL, second)


def test_malformed_and_unknown_inputs_get_the_same_error(setup):
    service, sender, _, _ = setup
    with pytest.raises(InvalidCodeError):
        service.verify_code("nobody@example.com", "123456")  # never requested
    service.request_code(EMAIL)
    with pytest.raises(InvalidCodeError):
        service.verify_code(EMAIL, "12ab56")


def test_requesting_codes_is_rate_limited(setup):
    service, _, _, _ = setup
    for _ in range(MAX_CODES_PER_WINDOW):
        service.request_code(EMAIL)
    with pytest.raises(TooManyAttemptsError):
        service.request_code(EMAIL)


@pytest.mark.parametrize("email", ["", "no-at-sign", "a@b", "a b@c.com", "x" * 300 + "@a.com"])
def test_bad_emails_are_rejected(email):
    with pytest.raises(RequestRejectedError):
        normalize_email(email)


# --- tokens ---------------------------------------------------------------


def make_signer(clock, secret=SECRET, ttl=timedelta(hours=1)):
    return TokenSigner(secret, ttl, clock)


def test_token_roundtrip_and_expiry(clock):
    signer = make_signer(clock)
    user_id = uuid4()
    token, _ = signer.issue(user_id)
    assert signer.verify(token) == user_id
    clock.advance(hours=1)
    with pytest.raises(InvalidTokenError, match="expired"):
        signer.verify(token)


def test_tampered_payload_is_rejected(clock):
    signer = make_signer(clock)
    token, _ = signer.issue(uuid4())
    version, body, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "=="))
    payload["sub"] = str(uuid4())  # impersonate someone else
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    with pytest.raises(InvalidTokenError, match="signature"):
        signer.verify(f"{version}.{forged}.{signature}")


def test_extended_expiry_is_rejected(clock):
    signer = make_signer(clock)
    token, _ = signer.issue(uuid4())
    version, body, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "=="))
    payload["exp"] += 10**6
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    with pytest.raises(InvalidTokenError):
        signer.verify(f"{version}.{forged}.{signature}")


def test_token_signed_with_another_secret_is_rejected(clock):
    token, _ = make_signer(clock, secret="other-secret").issue(uuid4())
    with pytest.raises(InvalidTokenError):
        make_signer(clock).verify(token)


@pytest.mark.parametrize(
    "token", ["", "garbage", "a.b", "v2.a.b", "v1.a.b.c", "v1..", "v1.%%%.@@@"]
)
def test_malformed_tokens_are_rejected(clock, token):
    with pytest.raises(InvalidTokenError):
        make_signer(clock).verify(token)


def test_a_code_hash_is_not_a_valid_token_signature(clock):
    """Sub-keys are separated by purpose: values do not cross over."""

    signer = make_signer(clock)
    token, _ = signer.issue(uuid4())
    version, body, _ = token.split(".")
    code_style = hash_code(SECRET, version + "." + body, "")
    with pytest.raises(InvalidTokenError):
        signer.verify(f"{version}.{body}.{code_style}")
