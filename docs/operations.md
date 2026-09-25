# Operations

## Processes

JobPilot runs as three independent long-lived processes, deliberately
not one monolith, so a slow or failing piece doesn't block the others:

1. **Webhook service** (`jobpilot.chat.webhook:create_app`) — a
   stateless FastAPI app. Scale horizontally behind a load balancer;
   it holds no in-process state (leases and delivery records live in
   the database), so any instance can handle any request.
2. **Scraper runners** (`jobpilot.ingest.worker.ScraperRunner`) — one
   process per platform (Talentflow, Hirebridge, Recruitly,
   Stackroll), run on a schedule (e.g. every few hours). Each is
   independently rate-limited via its own token bucket, so one
   platform slowing down or rate-limiting doesn't affect the others.
3. **Enrichment worker** (`jobpilot.ingest.worker.EnrichmentWorker`) —
   a long-running poller draining the ingestion queue. Scale the
   number of workers to the LLM provider's sustained throughput, not
   to scraper output — the queue absorbs the difference.

A background job (not included as a standalone process here, since it
composes existing pieces) periodically calls
`memory.extraction.extract_facts` over each conversation's recent
message window and writes results through `MemoryStore.remember`.

## Deploying a schema change

1. Add a new numbered migration file under `src/jobpilot/db/migrations/`
   — never edit a migration that has already shipped.
2. Migrations are additive by policy (see `CONTRIBUTING.md`): no
   dropping or renaming a column in the same migration that's still
   read by running code. If a column needs to go away, ship a
   migration that stops writing to it first, deploy, then ship a
   follow-up migration that drops it once nothing reads it.
3. Apply migrations in order against Supabase (via the SQL editor, the
   Supabase CLI, or your migration runner of choice) before deploying
   application code that depends on the new schema.

## Configuration and secrets

All configuration is environment variables (see `.env.example` and
`src/jobpilot/config.py`). Secrets (the LLM API key, Supabase service
role key, object storage keys, the webhook signing secret) should be
injected by whatever secrets manager the deployment platform provides
— they are never checked into the repository, and `Settings` defaults
to obvious placeholders specifically so a misconfigured deployment
fails fast (`LLMProviderError`, `RepositoryError`, etc.) instead of
silently calling the wrong endpoint.

## Observability

`jobpilot.logging.configure_logging` sets up structured logging
(`structlog`), JSON-formatted in any environment other than local
development. Every log call in the service layers binds relevant
context (`conversation_id`, `source_platform`, `content_hash`) rather
than interpolating it into a message string, so logs are filterable
without regex.

Key signals to alert on in a production deployment:

- `EnrichmentWorker` failure rate (`ScraperError` / `EnrichmentError`
  counts from `worker.py`) — a sustained spike usually means an
  upstream platform changed its response shape or the enrichment
  prompt is producing malformed output.
- Queue depth (`IngestQueue.depth()`) — a steadily growing depth means
  enrichment throughput is falling behind scrape volume.
- `turn_leases` row age — a lease that's been held past its
  `expires_at` without being released points at a worker that crashed
  mid-turn; it will self-heal once the lease naturally expires, but a
  pattern of this is worth investigating.
- `TurnBudgetExceededError` rate from the agent loop — a rising rate
  usually means the system prompt or a specific tool's output is
  leading the model into unproductive tool-calling loops.

## Rate limiting and retries

Each scraper's `TokenBucket` (`jobpilot/utils/ratelimit.py`) bounds
request rate to a single upstream platform; capacity and refill rate
are configured per deployment via
`JOBPILOT_SCRAPER_RATE_LIMIT_TOKENS_PER_SECOND` and
`JOBPILOT_SCRAPER_RATE_LIMIT_BUCKET_SIZE`. Retries against transient
failures use `jobpilot/utils/retry.py:retry_call`, which applies full
jitter exponential backoff (`JOBPILOT_RETRY_MAX_ATTEMPTS`,
`JOBPILOT_RETRY_BASE_DELAY_SECONDS`,
`JOBPILOT_RETRY_MAX_DELAY_SECONDS`) so retries from many scraper
instances don't synchronize into a thundering herd against a platform
that just recovered from an outage.

## Rollback

Application code is stateless and can be rolled back by redeploying
the previous version, as long as no additive-only migration
incompatibility was introduced (see the migration policy above — this
is exactly why migrations must stay additive). There is no destructive
rollback path for `jobs`, `messages`, or `user_facts` data; recovery
from a bad enrichment run is to re-run enrichment (raw postings remain
in object storage) rather than to restore from a database snapshot.
