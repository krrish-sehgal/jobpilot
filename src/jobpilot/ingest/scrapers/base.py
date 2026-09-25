"""`BaseScraper`: the contract every ATS-specific scraper implements.

A scraper's job is narrow: given an optional cursor, fetch the next
page of listings from one platform and return them as `RawPosting`s
plus the cursor to resume from. Everything else — rate limiting,
retrying, deduplication, checkpoint persistence, handing results to
the queue — is handled once, by `ScraperRunner` (see `worker.py`), so
individual scrapers stay small and platform-specific.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from jobpilot.models import RawPosting
from jobpilot.utils.hashing import content_hash
from jobpilot.utils.ratelimit import TokenBucket


@dataclass
class ScraperPage:
    """One page of results from a scraper, plus where to resume next."""

    postings: list[RawPosting]
    next_cursor: str | None
    has_more: bool


class BaseScraper(ABC):
    """Base class for a single-platform scraper.

    Subclasses implement `platform_name` and `fetch_page`; the base
    class owns rate limiting (`self._rate_limiter`) and the helper
    `_build_posting` that computes `content_hash` consistently so no
    subclass can accidentally hash the wrong fields.
    """

    def __init__(self, *, rate_limiter: TokenBucket | None = None) -> None:
        self._rate_limiter = rate_limiter or TokenBucket(refill_rate_per_second=2.0, capacity=10)

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """The invented ATS platform name this scraper targets."""

    @abstractmethod
    def fetch_page(self, cursor: str | None) -> ScraperPage:
        """Fetch one page of listings starting from `cursor`.

        `cursor is None` means "start from the beginning". Concrete
        implementations should call `self._rate_limiter.try_acquire()`
        (or block on `time_until_available`) before making a network
        request; the base class does not do this automatically since
        some platforms paginate with more than one request per page.
        """

    def _build_posting(
        self,
        *,
        source_listing_id: str,
        title: str,
        company: str,
        description: str,
        apply_url: str,
        location_text: str | None = None,
        posted_at=None,
    ) -> RawPosting:
        """Construct a `RawPosting` with a correctly computed content hash."""

        return RawPosting(
            source_platform=self.platform_name,
            source_listing_id=source_listing_id,
            title=title,
            company=company,
            description=description,
            location_text=location_text,
            posted_at=posted_at,
            apply_url=apply_url,
            content_hash=content_hash(title, company, description),
        )

    def iter_all_pages(self, *, start_cursor: str | None = None):
        """Yield `ScraperPage`s until the platform reports no more results."""

        cursor = start_cursor
        while True:
            page = self.fetch_page(cursor)
            yield page
            if not page.has_more or page.next_cursor is None:
                return
            cursor = page.next_cursor
