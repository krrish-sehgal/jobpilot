from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jobpilot.errors import CheckpointError
from jobpilot.ingest.checkpoint import CheckpointStore
from jobpilot.integrations.supabase_client import InMemoryDatabase


def test_load_returns_fresh_checkpoint_when_none_saved():
    store = CheckpointStore(InMemoryDatabase())
    checkpoint = store.load("talentflow")
    assert checkpoint.cursor is None
    assert checkpoint.postings_seen == 0


def test_advance_cursor_persists_progress_and_counters():
    store = CheckpointStore(InMemoryDatabase())
    store.advance_cursor(
        "talentflow", cursor="page-2", seen_delta=10, new_delta=8, duplicate_delta=2
    )
    checkpoint = store.load("talentflow")
    assert checkpoint.cursor == "page-2"
    assert checkpoint.postings_seen == 10
    assert checkpoint.postings_new == 8
    assert checkpoint.postings_duplicate == 2


def test_advance_cursor_accumulates_across_calls():
    store = CheckpointStore(InMemoryDatabase())
    store.advance_cursor("talentflow", cursor="page-1", seen_delta=5, new_delta=5)
    store.advance_cursor(
        "talentflow", cursor="page-2", seen_delta=5, new_delta=3, duplicate_delta=2
    )
    checkpoint = store.load("talentflow")
    assert checkpoint.postings_seen == 10
    assert checkpoint.postings_new == 8
    assert checkpoint.postings_duplicate == 2
    assert checkpoint.cursor == "page-2"


def test_restart_resumes_from_saved_cursor_not_from_scratch():
    store = CheckpointStore(InMemoryDatabase())
    store.advance_cursor("talentflow", cursor="page-5", seen_delta=50, new_delta=50)

    # Simulate a process restart: a fresh CheckpointStore instance over
    # the same database should still see the saved cursor.
    resumed = CheckpointStore(store._db)
    checkpoint = resumed.load("talentflow")
    assert checkpoint.cursor == "page-5"


def test_complete_run_without_start_raises():
    store = CheckpointStore(InMemoryDatabase())
    with pytest.raises(CheckpointError):
        store.complete_run("talentflow", now=datetime.now(UTC))


def test_start_then_complete_run_records_timestamps():
    store = CheckpointStore(InMemoryDatabase())
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
    store.start_run("talentflow", now=start)
    store.complete_run("talentflow", now=end)
    checkpoint = store.load("talentflow")
    assert checkpoint.last_run_started_at == start
    assert checkpoint.last_run_completed_at == end
