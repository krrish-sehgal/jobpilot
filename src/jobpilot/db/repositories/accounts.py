"""Repositories for website accounts and one-time sign-in codes.

A website account is a row in the existing `users` table that has an
`email`. Webhook-only users (no email) are untouched. `external_id` is
NOT NULL in 0001, so email accounts get the synthetic id
`email:<address>`; it also gives a natural uniqueness check in stores
that cannot express a partial unique index.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from jobpilot.errors import RecordNotFoundError
from jobpilot.integrations.supabase_client import Database
from jobpilot.models import AuthCode, LocationTier, SeniorityBand, UserAccount

_USERS = "users"
_AUTH_CODES = "auth_codes"


def _external_id(email: str) -> str:
    return f"email:{email}"


def _account_from_row(row: dict) -> UserAccount:
    return UserAccount(
        id=row["id"],
        email=row["email"],
        full_name=row.get("display_name"),
        seniority_band=row.get("seniority_band"),
        preferred_location_tiers=row.get("preferred_location_tiers") or [],
        created_at=row["created_at"],
    )


class UserAccountRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, user_id: UUID) -> UserAccount:
        row = self._db.get(_USERS, str(user_id))
        if not row.get("email"):
            raise RecordNotFoundError(f"user {user_id} has no website account")
        return _account_from_row(row)

    def find_by_email(self, email: str) -> UserAccount | None:
        rows = self._db.find(_USERS, external_id=_external_id(email))
        return _account_from_row(rows[0]) if rows else None

    def get_or_create_by_email(self, email: str, *, now: datetime) -> UserAccount:
        """Return the account for `email`, creating it on first sign-in.

        Callers pass an already-normalized (stripped, lower-cased)
        address; normalization lives in `web.auth` so there is one
        definition of "the same email".
        """

        existing = self.find_by_email(email)
        if existing is not None:
            return existing
        row = self._db.insert(
            _USERS,
            {
                "external_id": _external_id(email),
                "email": email,
                "display_name": None,
                "seniority_band": None,
                "preferred_location_tiers": [],
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        )
        return _account_from_row(row)

    def update_profile(
        self,
        user_id: UUID,
        *,
        full_name: str | None = None,
        seniority_band: SeniorityBand | None = None,
        preferred_location_tiers: list[LocationTier] | None = None,
    ) -> UserAccount:
        """Patch only the fields that were passed; `None` means "leave as is"."""

        patch: dict = {}
        if full_name is not None:
            patch["display_name"] = full_name
        if seniority_band is not None:
            patch["seniority_band"] = seniority_band.value
        if preferred_location_tiers is not None:
            patch["preferred_location_tiers"] = [t.value for t in preferred_location_tiers]
        row = (
            self._db.update(_USERS, str(user_id), patch)
            if patch
            else self._db.get(_USERS, str(user_id))
        )
        return _account_from_row(row)


class AuthCodeRepository:
    """Storage for one-time codes; policy (expiry, attempts) lives in `web.auth`."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, code: AuthCode) -> AuthCode:
        row = self._db.insert(_AUTH_CODES, code.model_dump(mode="json"))
        return AuthCode.model_validate(row)

    def update(self, code: AuthCode) -> AuthCode:
        row = self._db.update(_AUTH_CODES, str(code.id), code.model_dump(mode="json"))
        return AuthCode.model_validate(row)

    def list_for_email(self, email: str) -> list[AuthCode]:
        """All codes for `email`, newest first.

        Sorted ascending then reversed (rather than `reverse=True`) so
        that codes with identical timestamps keep insertion order and
        the later insert counts as newer.
        """

        codes = [AuthCode.model_validate(r) for r in self._db.find(_AUTH_CODES, email=email)]
        return list(reversed(sorted(codes, key=lambda c: c.created_at)))

    def latest_active(self, email: str) -> AuthCode | None:
        """The newest code that has not been consumed, or `None`.

        Only the newest code is ever valid: requesting a new code
        supersedes the old one, so an attacker cannot accumulate a pool
        of live codes to guess against.
        """

        for code in self.list_for_email(email):
            return code if code.consumed_at is None else None
        return None

    def count_since(self, email: str, since: datetime) -> int:
        return sum(1 for c in self.list_for_email(email) if c.created_at >= since)
