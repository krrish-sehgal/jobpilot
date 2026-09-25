"""Scraper for Hirebridge, an invented applicant tracking system.

Unlike Talentflow's cursor pagination, Hirebridge paginates with a
1-indexed `page` number and reports `total_pages` up front, so
`next_cursor` here is simply the next page number as a string.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

import httpx

from jobpilot.errors import ScraperParseError, ScraperRateLimitedError
from jobpilot.ingest.scrapers.base import BaseScraper, ScraperPage
from jobpilot.utils.ratelimit import TokenBucket

_DEFAULT_BASE_URL = "https://api.hirebridge.example.com"


class HirebridgeScraper(BaseScraper):
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
        return "hirebridge"

    def fetch_page(self, cursor: str | None) -> ScraperPage:
        if not self._rate_limiter.try_acquire():
            raise ScraperRateLimitedError(
                f"{self.platform_name}: local rate limit exhausted, retry later"
            )

        page_number = int(cursor) if cursor else 1
        response = self._http.get(
            f"{self._base_url}/api/jobs/search",
            params={"page": page_number, "per_page": 50},
        )
        if response.status_code == 429:
            raise ScraperRateLimitedError(f"{self.platform_name}: upstream returned 429")
        response.raise_for_status()

        try:
            payload = response.json()
            postings = [self._parse_job(item) for item in payload["jobs"]]
            total_pages = int(payload["total_pages"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ScraperParseError(f"{self.platform_name}: malformed jobs response") from exc

        has_more = page_number < total_pages
        next_cursor = str(page_number + 1) if has_more else None
        return ScraperPage(postings=postings, next_cursor=next_cursor, has_more=has_more)

    def _parse_job(self, item: dict[str, Any]) -> Any:
        try:
            return self._build_posting(
                source_listing_id=str(item["job_id"]),
                title=item["job_title"],
                company=item["company_name"],
                description=item["job_description"] or "",
                apply_url=item["application_url"],
                location_text=item.get("location_string"),
                posted_at=_parse_optional_epoch(item.get("posted_epoch")),
            )
        except KeyError as exc:
            raise ScraperParseError(f"{self.platform_name}: job missing field {exc}") from exc


def _parse_optional_epoch(value: int | None):
    if value is None:
        return None
    from datetime import datetime

    return datetime.fromtimestamp(value, tz=UTC)
