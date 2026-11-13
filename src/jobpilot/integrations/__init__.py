"""External system boundaries: LLM provider, object storage, queue, and
the Supabase client. Each integration is defined as a small protocol
plus a production implementation and an in-memory test double used
throughout the test suite."""
