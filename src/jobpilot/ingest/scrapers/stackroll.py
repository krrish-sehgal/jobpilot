"""Scraper for Stackroll, an invented applicant tracking system.

Stackroll's search endpoint uses offset-based pagination (`offset` /
`limit` / `total_count`) rather than a cursor token, which is the
simplest pagination style of the four platforms this codebase
targets and is kept as the reference implementation new scrapers are
usually copied from.
"""

from __future__ import annotations

from typing import Any

import httpx

from jobpilot.errors import ScraperParseError, ScraperRateLimitedError
from jobpilot.ingest.scrapers.base import BaseScraper, ScraperPage
from jobpilot.utils.ratelimit import TokenBucket

_DEFAULT_BASE_URL = "https://api.stackroll.example.com"
_PAGE_SIZE = 50


class StackrollScraper(BaseScraper):
    def __init__(
        self,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        http_client: httpx.Client | None = None,
        rate_limiter: TokenBucket | None = None,
    ) -> None:
        super().__init__(rate_limiter=rate_limiter)
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.Client(timeout=15.0)

    @property
    def platform_name(self) -> str:
        return "stackroll"

    def fetch_page(self, cursor: str | None) -> ScraperPage:
        if not self._rate_limiter.try_acquire():
            raise ScraperRateLimitedError(
                f"{self.platform_name}: local rate limit exhausted, retry later"
            )

        offset = int(cursor) if cursor else 0
        response = self._http.get(
            f"{self._base_url}/postings",
            params={"offset": offset, "limit": _PAGE_SIZE},
        )
        if response.status_code == 429:
            raise ScraperRateLimitedError(f"{self.platform_name}: upstream returned 429")
        response.raise_for_status()

        try:
            payload = response.json()
            postings = [self._parse_posting(item) for item in payload["items"]]
            total_count = int(payload["total_count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ScraperParseError(f"{self.platform_name}: malformed postings response") from exc

        next_offset = offset + len(postings)
        has_more = next_offset < total_count and len(postings) > 0
        next_cursor = str(next_offset) if has_more else None
        return ScraperPage(postings=postings, next_cursor=next_cursor, has_more=has_more)

    def _parse_posting(self, item: dict[str, Any]) -> Any:
        try:
            return self._build_posting(
                source_listing_id=str(item["posting_id"]),
                title=item["role_title"],
                company=item["org_name"],
                description=item["body_text"] or "",
                apply_url=item["external_apply_link"],
                location_text=item.get("location_label"),
                posted_at=_parse_optional_datetime(item.get("created_at")),
            )
        except KeyError as exc:
            raise ScraperParseError(f"{self.platform_name}: posting missing field {exc}") from exc


def _parse_optional_datetime(value: str | None):
    if not value:
        return None
    from dateutil import parser as date_parser

    return date_parser.isoparse(value)
