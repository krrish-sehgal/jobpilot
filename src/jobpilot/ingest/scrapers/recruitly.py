"""Scraper for Recruitly, an invented applicant tracking system.

Recruitly's public feed is a GraphQL endpoint returning a Relay-style
connection (`edges` / `pageInfo.endCursor` / `pageInfo.hasNextPage`),
which this scraper adapts to the shared `ScraperPage` contract.
"""

from __future__ import annotations

from typing import Any

import httpx

from jobpilot.errors import ScraperParseError, ScraperRateLimitedError
from jobpilot.ingest.scrapers.base import BaseScraper, ScraperPage
from jobpilot.utils.ratelimit import TokenBucket

_DEFAULT_BASE_URL = "https://api.recruitly.example.com"

_LISTINGS_QUERY = """
query Listings($after: String) {
  listings(first: 50, after: $after) {
    edges { node { id title employerName descriptionText applyUrl city remote publishedAt } }
    pageInfo { endCursor hasNextPage }
  }
}
"""


class RecruitlyScraper(BaseScraper):
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
        return "recruitly"

    def fetch_page(self, cursor: str | None) -> ScraperPage:
        if not self._rate_limiter.try_acquire():
            raise ScraperRateLimitedError(
                f"{self.platform_name}: local rate limit exhausted, retry later"
            )

        response = self._http.post(
            f"{self._base_url}/graphql",
            json={"query": _LISTINGS_QUERY, "variables": {"after": cursor}},
        )
        if response.status_code == 429:
            raise ScraperRateLimitedError(f"{self.platform_name}: upstream returned 429")
        response.raise_for_status()

        try:
            payload = response.json()
            connection = payload["data"]["listings"]
            postings = [self._parse_node(edge["node"]) for edge in connection["edges"]]
            page_info = connection["pageInfo"]
            has_more = bool(page_info["hasNextPage"])
            next_cursor = page_info.get("endCursor")
        except (KeyError, TypeError, ValueError) as exc:
            raise ScraperParseError(f"{self.platform_name}: malformed GraphQL response") from exc

        return ScraperPage(postings=postings, next_cursor=next_cursor, has_more=has_more)

    def _parse_node(self, node: dict[str, Any]) -> Any:
        try:
            location = "Remote" if node.get("remote") else node.get("city")
            return self._build_posting(
                source_listing_id=str(node["id"]),
                title=node["title"],
                company=node["employerName"],
                description=node["descriptionText"] or "",
                apply_url=node["applyUrl"],
                location_text=location,
                posted_at=_parse_optional_datetime(node.get("publishedAt")),
            )
        except KeyError as exc:
            raise ScraperParseError(f"{self.platform_name}: node missing field {exc}") from exc


def _parse_optional_datetime(value: str | None):
    if not value:
        return None
    from dateutil import parser as date_parser

    return date_parser.isoparse(value)
