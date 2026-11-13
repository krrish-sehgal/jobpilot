"""Email one-time-code sign-in and signed access tokens.

No password, no third-party identity provider, and no new dependency:
a six-digit code is emailed, exchanged once for a bearer token, and the
token is verified on every request by recomputing an HMAC.

Security decisions, in brief:

* **Codes are hashed at rest** with HMAC-SHA256 keyed by the server
  secret and bound to the email. Six digits is only a million guesses,
  so an unkeyed hash would be reversible from a leaked table in
  milliseconds; the key makes the database alone useless.
* **Codes are short-lived and attempt-limited**: ten minutes, five wrong
  guesses, then the code is dead and the user must request another.
  Requesting a code supersedes older ones, and requests are capped per
  email, so neither guessing nor spamming scales.
* **Verification failures are uniform**: unknown email, no live code and
  wrong code all say "invalid or expired code", so the endpoint cannot be
  used to learn which addresses have accounts.
* **Tokens are a small signed envelope**, `v1.<payload>.<signature>`
  (JWT-shaped, but with a fixed algorithm so there is no `alg` header to
  confuse). The signature is checked with `hmac.compare_digest` *before*
  the payload is parsed. Separate sub-keys are derived for codes and
  tokens so a value from one can never be replayed as the other.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from jobpilot.db.repositories.accounts import AuthCodeRepository, UserAccountRepository
from jobpilot.errors import (
    CodeExpiredError,
    InvalidCodeError,
    InvalidTokenError,
    RequestRejectedError,
    TooManyAttemptsError,
)
from jobpilot.logging import get_logger
from jobpilot.models import AuthCode, UserAccount

logger = get_logger(__name__)

CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=10)
MAX_VERIFY_ATTEMPTS = 5
MAX_CODES_PER_WINDOW = 5
CODE_REQUEST_WINDOW = timedelta(minutes=15)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TOKEN_VERSION = "v1"


def normalize_email(email: str) -> str:
    """Trim and lower-case; reject anything that is plainly not an address."""

    cleaned = email.strip().lower()
    if len(cleaned) > 254 or not _EMAIL_RE.match(cleaned):
        raise RequestRejectedError("enter a valid email address")
    return cleaned


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _subkey(secret: str, label: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), label.encode("ascii"), hashlib.sha256).digest()


def hash_code(secret: str, email: str, code: str) -> str:
    key = _subkey(secret, "jobpilot/auth-code")
    return hmac.new(key, f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


class TokenSigner:
    """Issues and verifies bearer tokens."""

    def __init__(
        self,
        secret: str,
        ttl: timedelta,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._key = _subkey(secret, "jobpilot/access-token")
        self._ttl = ttl
        self._clock = clock

    def issue(self, user_id: UUID) -> tuple[str, datetime]:
        now = self._clock()
        expires_at = now + self._ttl
        payload = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{_TOKEN_VERSION}.{body}"
        return f"{signing_input}.{self._sign(signing_input)}", expires_at

    def verify(self, token: str) -> UUID:
        """Return the user id in `token`, or raise `InvalidTokenError`."""

        parts = token.split(".")
        if len(parts) != 3 or parts[0] != _TOKEN_VERSION:
            raise InvalidTokenError("malformed token")
        version, body, signature = parts
        expected = self._sign(f"{version}.{body}")
        if not hmac.compare_digest(expected, signature):
            raise InvalidTokenError("invalid token signature")
        try:
            payload = json.loads(_unb64(body))
            expires = int(payload["exp"])
            user_id = UUID(payload["sub"])
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidTokenError("malformed token payload") from exc
        if self._clock().timestamp() >= expires:
            raise InvalidTokenError("token expired")
        return user_id

    def _sign(self, signing_input: str) -> str:
        return _b64(hmac.new(self._key, signing_input.encode("ascii"), hashlib.sha256).digest())


class CodeSender(Protocol):
    """Delivers a sign-in code. Production implements this over SES/SMTP."""

    def send_code(self, email: str, code: str) -> None: ...


class LoggingCodeSender:
    """Development sender: writes the code to the log instead of emailing it.

    The code is only logged outside production, so a misconfigured
    deployment degrades to "nobody can sign in" rather than "codes are in
    the logs".
    """

    def __init__(self, *, log_code: bool) -> None:
        self._log_code = log_code

    def send_code(self, email: str, code: str) -> None:
        logger.info("auth_code_issued", email=email, code=code if self._log_code else "<hidden>")


class RecordingCodeSender:
    """Test sender that remembers the latest code per email."""

    def __init__(self) -> None:
        self.codes: dict[str, str] = {}

    def send_code(self, email: str, code: str) -> None:
        self.codes[email] = code


class AuthService:
    def __init__(
        self,
        *,
        accounts: UserAccountRepository,
        codes: AuthCodeRepository,
        signer: TokenSigner,
        sender: CodeSender,
        secret: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._accounts = accounts
        self._codes = codes
        self._signer = signer
        self._sender = sender
        self._secret = secret
        self._clock = clock

    def request_code(self, email: str) -> None:
        email = normalize_email(email)
        now = self._clock()
        if self._codes.count_since(email, now - CODE_REQUEST_WINDOW) >= MAX_CODES_PER_WINDOW:
            raise TooManyAttemptsError("too many codes requested, try again later")

        # Retire any live code first, so only the newest one can ever work.
        previous = self._codes.latest_active(email)
        if previous is not None:
            self._codes.update(previous.model_copy(update={"consumed_at": now}))

        code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
        self._codes.save(
            AuthCode(
                email=email,
                code_hash=hash_code(self._secret, email, code),
                expires_at=now + CODE_TTL,
                created_at=now,
            )
        )
        self._sender.send_code(email, code)

    def verify_code(self, email: str, code: str) -> tuple[str, datetime, UserAccount]:
        email = normalize_email(email)
        now = self._clock()
        stored = self._codes.latest_active(email)
        if stored is None or not re.fullmatch(rf"\d{{{CODE_LENGTH}}}", code.strip()):
            raise InvalidCodeError("invalid or expired code")
        if stored.attempts >= MAX_VERIFY_ATTEMPTS:
            raise TooManyAttemptsError("too many wrong attempts, request a new code")
        if now >= stored.expires_at:
            raise CodeExpiredError("invalid or expired code")

        expected = hash_code(self._secret, email, code.strip())
        if not hmac.compare_digest(expected, stored.code_hash):
            attempts = stored.attempts + 1
            self._codes.update(stored.model_copy(update={"attempts": attempts}))
            if attempts >= MAX_VERIFY_ATTEMPTS:
                raise TooManyAttemptsError("too many wrong attempts, request a new code")
            raise InvalidCodeError("invalid or expired code")

        self._codes.update(stored.model_copy(update={"consumed_at": now}))
        user = self._accounts.get_or_create_by_email(email, now=now)
        token, expires_at = self._signer.issue(user.id)
        return token, expires_at, user
