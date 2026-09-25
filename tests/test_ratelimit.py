from __future__ import annotations

import pytest

from jobpilot.utils.ratelimit import TokenBucket


def test_token_bucket_starts_full():
    clock = {"t": 0.0}
    bucket = TokenBucket(refill_rate_per_second=1.0, capacity=5, clock=lambda: clock["t"])
    assert bucket.available_tokens == 5


def test_token_bucket_depletes_on_acquire():
    clock = {"t": 0.0}
    bucket = TokenBucket(refill_rate_per_second=1.0, capacity=5, clock=lambda: clock["t"])
    for _ in range(5):
        assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False


def test_token_bucket_refills_over_time():
    clock = {"t": 0.0}
    bucket = TokenBucket(refill_rate_per_second=2.0, capacity=5, clock=lambda: clock["t"])
    for _ in range(5):
        bucket.try_acquire()
    assert bucket.try_acquire() is False
    clock["t"] += 1.0  # 2 tokens/sec * 1s = 2 tokens refilled
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False


def test_token_bucket_never_exceeds_capacity():
    clock = {"t": 0.0}
    bucket = TokenBucket(refill_rate_per_second=10.0, capacity=3, clock=lambda: clock["t"])
    clock["t"] += 100.0
    assert bucket.available_tokens == 3


def test_time_until_available():
    clock = {"t": 0.0}
    bucket = TokenBucket(refill_rate_per_second=1.0, capacity=1, clock=lambda: clock["t"])
    bucket.try_acquire()
    assert bucket.time_until_available() == pytest.approx(1.0)


def test_token_bucket_rejects_invalid_config():
    with pytest.raises(ValueError):
        TokenBucket(refill_rate_per_second=0, capacity=1)
    with pytest.raises(ValueError):
        TokenBucket(refill_rate_per_second=1, capacity=0)
