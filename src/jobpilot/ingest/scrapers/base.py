"""
Base class for scrapers.

The key architectural idea here: a scraper targets an applicant
tracking system (the hiring software many companies share to post and
manage job openings), not a single company. Because dozens or hundreds
of employers all publish their postings through the same handful of
ATS platforms, one scraper written against one ATS's public posting
pages reaches every employer that happens to use it — instead of
needing a bespoke scraper per company.

This module defines the shared shape; scrapers/demo_ats.py shows one
concrete (fake) example.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawPosting:
    """A job posting exactly as scraped, before any enrichment. This is
    what gets written to object storage and then queued for a worker
    to enrich — see queue.py and enrich.py."""

    source_ats: str
    source_posting_id: str
    company_name: str
    raw_text: str
    posting_url: str
    scraped_at: datetime


class BaseScraper(ABC):
    """One subclass per applicant tracking system, not per company.

    A subclass is responsible for knowing how that ATS's public
    postings pages are structured (or its public API, where one
    exists) and turning whatever it finds into a list of RawPosting
    objects. Everything downstream of that — storage, queueing,
    enrichment — is shared and does not need to know which ATS a
    posting came from.
    """

    #: Short identifier for the ATS this scraper targets, e.g. "demo_ats".
    #: Stored on every RawPosting it produces so later steps can trace
    #: a record back to its source.
    source_name: str

    @abstractmethod
    def list_open_postings(self, *, limit: int | None = None) -> list[RawPosting]:
        """Return raw postings currently visible on the target ATS.

        Real implementations would page through a public listing
        endpoint or search page for the ATS and stop once `limit` is
        reached (or the listing runs out).
        """
        raise NotImplementedError

    def run(self) -> list[RawPosting]:
        """Convenience entry point a scheduler would call. Left as a
        thin wrapper around list_open_postings so subclasses only need
        to implement the one method."""
        return self.list_open_postings()
