"""
A single example scraper, targeting a made-up "Demo ATS" platform.

This is the only scraper implemented in this demo repo. It returns a
few hardcoded fake postings instead of making any network call, since
nothing in this project is meant to run. A real scraper for a real ATS
would replace list_open_postings with actual HTTP calls and HTML/JSON
parsing.
"""

from __future__ import annotations

from datetime import datetime, timezone

from jobpilot.ingest.scrapers.base import BaseScraper, RawPosting


class DemoATSScraper(BaseScraper):
    """Targets the fictional 'Demo ATS' platform. Any company using
    Demo ATS to post openings would be reachable through this one
    scraper — that's the point of scraping by platform, not by company.
    """

    source_name = "demo_ats"

    def list_open_postings(self, *, limit: int | None = None) -> list[RawPosting]:
        """Return a small, fixed set of fake postings.

        In a real scraper this would fetch Demo ATS's public postings
        listing and parse each result into a RawPosting. Here it just
        returns invented examples so downstream code (queue, worker,
        enrich) has something to point at.
        """
        now = datetime.now(timezone.utc)
        postings = [
            RawPosting(
                source_ats=self.source_name,
                source_posting_id="demo-ats-posting-001",
                company_name="Fictional Widgets Co",
                raw_text=(
                    "We're hiring a Data Analyst to join our small team. "
                    "You'll pull reports, build dashboards, and work "
                    "closely with the ops team. 0-2 years experience is "
                    "fine. Remote friendly. Pay: not listed."
                ),
                posting_url="https://example.com/careers/demo-ats-posting-001",
                scraped_at=now,
            ),
            RawPosting(
                source_ats=self.source_name,
                source_posting_id="demo-ats-posting-002",
                company_name="Example Robotics Inc",
                raw_text=(
                    "Senior Backend Engineer wanted. 6+ years building "
                    "backend systems, comfortable owning a service "
                    "end to end. Hybrid, must be near our fictional "
                    "office. Compensation range: placeholder-not-real."
                ),
                posting_url="https://example.com/careers/demo-ats-posting-002",
                scraped_at=now,
            ),
            RawPosting(
                source_ats=self.source_name,
                source_posting_id="demo-ats-posting-003",
                company_name="Sample Logistics Group",
                raw_text=(
                    "Customer Support rep needed, entry level, no "
                    "experience required, training provided. Urgent "
                    "hiring, apply now and start earning immediately! "
                    "Just send your bank details to get started."
                ),
                posting_url="https://example.com/careers/demo-ats-posting-003",
                scraped_at=now,
            ),
        ]
        return postings[:limit] if limit is not None else postings
