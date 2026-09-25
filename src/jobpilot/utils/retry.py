"""Retry with exponential backoff and full jitter.

Implements the "full jitter" strategy from AWS's backoff-and-jitter
writeup: each retry sleeps a random duration between 0 and the
exponential cap, rather than a fixed exponential value. This spreads
out retries from many callers so they don't all hammer the upstream
service in synchronized bursts after a shared outage.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_DEFAULT_RNG = random.Random()


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been used up."""

    def __init__(self, attempts: int, last_exception: BaseException) -> None:
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(f"retry exhausted after {attempts} attempts: {last_exception!r}")


def compute_backoff_delay(
    attempt: int,
    *,
    base_delay_seconds: float,
    max_delay_seconds: float,
    rng: random.Random | None = None,
) -> float:
    """Return the jittered delay (seconds) to sleep before `attempt`.

    `attempt` is 1-indexed (the delay before the *first* retry, i.e.
    the second overall attempt, is `attempt=1`). The exponential cap
    is `base_delay_seconds * 2 ** (attempt - 1)`, clamped to
    `max_delay_seconds`; the actual delay is drawn uniformly from
    `[0, cap]` (full jitter).
    """

    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    active_rng = rng if rng is not None else _DEFAULT_RNG
    cap = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
    return active_rng.uniform(0, cap)


def retry_call(
    fn: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay_seconds: float = 0.5,
    max_delay_seconds: float = 20.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> T:
    """Call `fn`, retrying with jittered exponential backoff on failure.

    Re-raises as `RetryExhaustedError` once `max_attempts` is used up,
    preserving the last exception for inspection. Exceptions not in
    `retry_on` propagate immediately without consuming a retry.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_exception: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except retry_on as exc:
            last_exception = exc
            if attempt == max_attempts:
                break
            delay = compute_backoff_delay(
                attempt,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
                rng=rng,
            )
            sleep(delay)

    assert last_exception is not None
    raise RetryExhaustedError(max_attempts, last_exception)
