# JobPilot

JobPilot is an agentic job-search assistant. A conversational agent
helps a user find and evaluate roles by calling tools rather than
generating text from nothing; underneath it, an ingestion pipeline
pulls postings from several applicant tracking systems, enriches them
into a strict taxonomy with an LLM, and a hybrid search and ranking
engine serves matches back through the agent.

## What's here

```
jobpilot/
  src/jobpilot/
    agent/          agentic loop: tool registry, tools, prompts, turn budget
    chat/            inbound webhook, claim-and-lease orchestration, outbound ledger, cards
    memory/          background fact extraction + semantic recall
    ingest/          scrapers, dedup, checkpointing, queue consumer, LLM enrichment
    search/          embeddings, hybrid retrieval, the ranking engine
    db/              repository layer + SQL migrations
    integrations/    LLM / object storage / queue / Supabase boundaries (+ fakes)
    utils/           retry/backoff, rate limiting, hashing, text chunking
  db/migrations/      (see src/jobpilot/db/migrations)
  docs/               architecture, data model, operations
  tests/              unit tests against the pure logic and the fakes
```

## The core ideas

1. **Agentic loop, not a single generation.** The agent has four
   tools — `search_jobs`, `recall_memory`, `fetch_resume`,
   `get_job_details` — and decides which to call, looks at the
   result, and decides again, bounded by a turn budget so it always
   terminates. See `src/jobpilot/agent/loop.py`.
2. **Durable conversations.** An inbound message is persisted before
   anything else happens to it. A claim-and-lease mechanism
   (`chat/orchestrator.py`) guarantees only one worker processes a
   given turn even if the same message is delivered twice, and an
   idempotency-keyed delivery ledger (`chat/ledger.py`) guarantees the
   user is never sent the same reply twice either.
3. **Long-term memory.** A background step extracts durable facts
   about a user from conversation history (`memory/extraction.py`)
   and stores them for later semantic recall (`memory/store.py`),
   so the agent doesn't ask a returning user to repeat themselves.
4. **Ingestion by platform.** Four scrapers, one per invented
   applicant tracking system (Talentflow, Hirebridge, Recruitly,
   Stackroll), share a `BaseScraper` contract. A scraper reaches
   every employer on that platform in one crawl. Raw postings flow
   through object storage and a queue to an enrichment worker, so
   scraping and enrichment scale independently and a restart resumes
   from a checkpoint instead of re-crawling.
5. **Enrichment against a fixed taxonomy.** An LLM call turns messy
   posting text into a `JobRecord` — 8 role categories, 5 seniority
   bands mapped to year ranges, skills, location tier, pay, and a
   fraud-signal check — and the result is validated hard against that
   taxonomy before it's ever stored.
6. **The matching idea.** Rather than embedding the job description,
   enrichment has the LLM write a short description of the *ideal
   candidate* for the role — company and location stripped out — and
   that's what gets embedded (`candidate_profile_text`). A job seeker
   describes themselves in the same register they'd want matched
   against, so person-to-person comparison outperforms
   query-to-job-ad comparison. The full reasoning is in
   [`docs/architecture.md`](docs/architecture.md).
7. **Hybrid search and ranking.** Structured filters (role, seniority,
   location tier, employment type, pay floor, fraud exclusion) narrow
   the candidate set before semantic similarity ever runs, and five
   weighted signals — semantic similarity, recency, seniority fit,
   location fit, and posting completeness — combine into a single
   ranked score (`search/ranking.py`).

## Local setup

```bash
git clone https://github.com/krrish-sehgal/jobpilot.git
cd jobpilot
python -m venv .venv && source .venv/bin/activate
make install
cp .env.example .env
make test
```

The test suite runs entirely against in-memory fakes
(`FakeLLMClient`, `InMemoryDatabase`, `InMemoryQueueBackend`,
`InMemoryObjectStorage`) and requires no external credentials. Filling
in `.env` with real Supabase, LLM, storage, and queue credentials is
only needed to run the webhook service or the ingestion workers
against live infrastructure.

```bash
make lint      # ruff
make test      # pytest
make run       # start the webhook service (needs a real database configured)
```

## Configuration

All configuration is environment variables read by
`src/jobpilot/config.py` via `pydantic-settings`, prefixed
`JOBPILOT_`. See `.env.example` for the full list — LLM provider and
model, Supabase project, object storage bucket, queue backend,
webhook signing secret, agent turn budget, and ranking weights.

## Data model

See [`docs/data-model.md`](docs/data-model.md) for the full schema.
In brief: `users`, `jobs` (with the taxonomy columns and a pgvector
embedding of `candidate_profile_text`), `messages` / `conversations`
/ `turn_leases` / `outbound_deliveries` for the chat pipeline,
`user_facts` for memory, `ingest_checkpoints` for resumable scraping,
and `match_scores` for persisted ranking output.

## Testing

```bash
make test
make coverage
```

Tests cover the pure logic directly: ranking math, hybrid-search
filtering, content-hash dedup, retry/backoff jitter bounds, the token
bucket, text chunking, enrichment schema validation, the tool
registry's argument validation, the agent loop's turn budget, the
orchestrator's claim-and-lease behavior, and the delivery ledger's
idempotency guarantee.

## Deployment notes

See [`docs/operations.md`](docs/operations.md) for how the pieces are
meant to run in production: the webhook service as a small stateless
API, the enrichment worker and scraper runners as separate long-lived
processes (so a slow LLM provider never blocks scraping), and the
migration order in `db/migrations/`.

## License

MIT.
