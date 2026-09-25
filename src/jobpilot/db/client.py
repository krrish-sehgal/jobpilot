"""
Database client placeholder.

Supabase is the only database in this project — there is no separate
cache, no separate vector store, no separate queue backend implied
here. Everything the rest of the codebase treats as "the database"
would go through a client built like this one.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class SupabaseConfig:
    """Connection settings read from the environment. See .env.example
    for the placeholder values these would come from."""

    url: str
    service_key: str

    @classmethod
    def from_env(cls) -> "SupabaseConfig":
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            raise NotImplementedError(
                "demo only: SUPABASE_URL / SUPABASE_SERVICE_KEY are placeholders, "
                "not a real connection"
            )
        return cls(url=url, service_key=key)


class SupabaseClient:
    """Stand-in for a real Supabase client object. Every method raises
    — this class exists only so other modules have something concrete
    to type-hint against and import, showing where a database call
    would be made without ever making one.
    """

    def __init__(self, config: SupabaseConfig):
        self.config = config

    def table(self, name: str) -> "SupabaseClient":
        """Would normally return a query builder scoped to `name`."""
        raise NotImplementedError("demo only: no real database is connected")

    def rpc(self, function_name: str, params: dict) -> None:
        """Would normally call a Postgres function through PostgREST."""
        raise NotImplementedError("demo only: no real database is connected")


def get_client() -> SupabaseClient:
    """Build a SupabaseClient from environment configuration. Every
    other module in this project that needs "the database" would call
    this function rather than constructing a client itself.
    """
    return SupabaseClient(SupabaseConfig.from_env())
