from __future__ import annotations

import random

import pytest

from jobpilot.utils.retry import RetryExhaustedError, compute_backoff_delay, retry_call


def test_compute_backoff_delay_within_exponential_cap():
    rng = random.Random(42)
    for attempt in range(1, 6):
        delay = compute_backoff_delay(
            attempt, base_delay_seconds=1.0, max_delay_seconds=100.0, rng=rng
        )
        cap = min(100.0, 1.0 * (2 ** (attempt - 1)))
        assert 0 <= delay <= cap


def test_compute_backoff_delay_respects_max_delay():
    rng = random.Random(1)
    delay = compute_backoff_delay(20, base_delay_seconds=1.0, max_delay_seconds=5.0, rng=rng)
    assert delay <= 5.0


def test_compute_backoff_delay_rejects_invalid_attempt():
    with pytest.raises(ValueError):
        compute_backoff_delay(0, base_delay_seconds=1.0, max_delay_seconds=5.0)


def test_retry_call_succeeds_after_transient_failures():
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ConnectionError("transient")
        return "ok"

    sleeps = []
    result = retry_call(
        flaky, max_attempts=5, base_delay_seconds=0.01, max_delay_seconds=0.02, sleep=sleeps.append
    )
    assert result == "ok"
    assert calls["count"] == 3
    assert len(sleeps) == 2


def test_retry_call_raises_retry_exhausted():
    def always_fails():
        raise ConnectionError("nope")

    with pytest.raises(RetryExhaustedError) as excinfo:
        retry_call(
            always_fails,
            max_attempts=3,
            base_delay_seconds=0.01,
            max_delay_seconds=0.01,
            sleep=lambda _s: None,
        )
    assert excinfo.value.attempts == 3


def test_retry_call_does_not_retry_unlisted_exceptions():
    def raises_value_error():
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        retry_call(
            raises_value_error,
            retry_on=(ConnectionError,),
            sleep=lambda _s: None,
        )
