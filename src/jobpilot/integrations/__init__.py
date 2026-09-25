"""External system boundaries: LLM provider, object storage, queue, and
the Supabase client. Each integration is defined as a small protocol
plus a real (unconfigured) implementation and an in-memory fake used
throughout the test suite."""
