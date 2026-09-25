"""Database client factory.

`get_database` returns the `Database` implementation appropriate for
the current settings. Production code and tests both call this single
entry point rather than constructing `SupabaseDatabase` or
`InMemoryDatabase` directly, so swapping backends never requires
touching a repository.
"""

from __future__ import annotations

from jobpilot.config import Settings, get_settings
from jobpilot.integrations.supabase_client import Database, InMemoryDatabase, SupabaseDatabase


def get_database(settings: Settings | None = None) -> Database:
    settings = settings or get_settings()
    if settings.environment == "test":
        return InMemoryDatabase()
    return SupabaseDatabase(settings)
