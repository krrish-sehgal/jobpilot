"""Token bucket rate limiter.

Used to bound outbound request rate to a single upstream ATS platform
during scraping, independent of wall-clock sleeps scattered through
scraper code. The bucket refills continuously based on elapsed time,
so bursts up to `capacity` are allowed but the long-run rate is capped
at `refill_rate_per_second`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class TokenBucket:
    """A thread-safe token bucket rate limiter."""

    def __init__(
        self,
        *,
        refill_rate_per_second: float,
        capacity: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if refill_rate_per_second <= 0:
            raise ValueError("refill_rate_per_second must be > 0")
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._refill_rate = refill_rate_per_second
        self._capacity = float(capacity)
        self._clock = clock
        self._tokens = float(capacity)
        self._last_refill = clock()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last_refill)
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def try_acquire(self, tokens: int = 1) -> bool:
        """Attempt to consume `tokens` without blocking.

        Returns True and deducts the tokens if enough were available,
        otherwise returns False and leaves the bucket unchanged.
        """

        if tokens < 1:
            raise ValueError("tokens must be >= 1")
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def time_until_available(self, tokens: int = 1) -> float:
        """Seconds until `tokens` would be available, 0 if available now."""

        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                return 0.0
            deficit = tokens - self._tokens
            return deficit / self._refill_rate

    @property
    def available_tokens(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens
