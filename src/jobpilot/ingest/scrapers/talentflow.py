"""Scraper for Talentflow, an invented applicant tracking system.

Talentflow exposes a public JSON listings endpoint per employer
career site, paginated with an opaque `next` cursor token. This
scraper targets Talentflow's aggregate search endpoint, which fans
out across every employer on the platform in one paginated stream.
"""

from __future__ import annotations

from typing import Any

import httpx

from jobpilot.errors import ScraperParseError, ScraperRateLimitedError
from jobpilot.ingest.scrapers.base import BaseScraper, ScraperPage
from jobpilot.utils.ratelimit import TokenBucket

_DEFAULT_BASE_URL = "https://api.talentflow.example.com"


class TalentflowScraper(BaseScraper):
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
        return "talentflow"

    def fetch_page(self, cursor: str | None) -> ScraperPage:
        if not self._rate_limiter.try_acquire():
            raise ScraperRateLimitedError(
                f"{self.platform_name}: local rate limit exhausted, retry later"
            )

        params: dict[str, Any] = {"limit": 50}
        if cursor:
            params["cursor"] = cursor

        response = self._http.get(f"{self._base_url}/v1/listings", params=params)
        if response.status_code == 429:
            raise ScraperRateLimitedError(f"{self.platform_name}: upstream returned 429")
        response.raise_for_status()

        try:
            payload = response.json()
            postings = [self._parse_listing(item) for item in payload["results"]]
            next_cursor = payload.get("next_cursor")
            has_more = bool(payload.get("has_more", False))
        except (KeyError, TypeError, ValueError) as exc:
            raise ScraperParseError(f"{self.platform_name}: malformed listings response") from exc

        return ScraperPage(postings=postings, next_cursor=next_cursor, has_more=has_more)

    def _parse_listing(self, item: dict[str, Any]) -> Any:
        try:
            return self._build_posting(
                source_listing_id=str(item["id"]),
                title=item["title"],
                company=item["employer"]["name"],
                description=item["description_html"] or "",
                apply_url=item["apply_url"],
                location_text=item.get("location", {}).get("display_name"),
                posted_at=_parse_optional_datetime(item.get("posted_at")),
            )
        except KeyError as exc:
            raise ScraperParseError(f"{self.platform_name}: listing missing field {exc}") from exc


def _parse_optional_datetime(value: str | None):
    if not value:
        return None
    from dateutil import parser as date_parser

    return date_parser.isoparse(value)
