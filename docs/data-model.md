# Data model

Full DDL lives in `src/jobpilot/db/migrations/`. This document is the
narrative version: what each table is for and how they relate.

## Entity overview

```
users ──< conversations ──< messages
  │                              │
  │                        turn_leases (1:1 with conversations, transient)
  │                              │
  │                        outbound_deliveries
  │
  └──< user_facts (memory)

jobs ──< match_scores >── users
  │
ingest_checkpoints (per source_platform, not FK'd to jobs)
```

## `users`

One row per person the agent talks to. `external_id` is the stable
identifier from whatever channel/auth system sits in front of
JobPilot (kept generic here since that integration is
deployment-specific).

## `jobs`

The canonical enriched posting, one row per unique `content_hash`
(see `jobs_content_hash_unique`). Columns split into three groups:

- **Source identity**: `source_platform`, `source_listing_id`,
  `content_hash`, `apply_url` — where this posting came from and how
  to detect a re-scrape of the same content.
- **Taxonomy fields**: `role_category`, `seniority_band`,
  `min_years_experience`, `skills`, `location_tier`,
  `employment_type`, `compensation_*`, `fraud_signal` — all
  constrained by `check` clauses matching the enums in
  `jobpilot/models.py`. A value outside the taxonomy fails at the
  database layer, not just at the application layer, as a second line
  of defense against a future write path that skips
  `JobRecord` validation.
- **Matching**: `candidate_profile_text` (the LLM-authored
  ideal-candidate description — see `docs/architecture.md`) and
  `candidate_profile_embedding vector(1536)`, indexed with an
  `ivfflat` approximate-nearest-neighbour index for similarity search
  at scale.

## `ingest_checkpoints`

One row per `source_platform`, holding the pagination `cursor` to
resume from and running counters (`postings_seen`, `postings_new`,
`postings_duplicate`). Not foreign-keyed to `jobs` — a checkpoint
describes crawl progress, which outlives any individual posting.

## `conversations` / `messages`

A `conversation` groups a user's message history. Each `message` has
a `direction` (`inbound`/`outbound`) and a `status`
(`received` → `processing` → `processed`, or `failed`). Messages are
never updated in place except for `status` — the body is immutable
once written, since it's the durable record of what was actually
said.

## `turn_leases`

At most one row per `conversation_id` (it's the primary key), holding
`worker_id`, `claimed_at`, `expires_at`. This table is transient
working state, not an audit log — a row is deleted once the
orchestrator finishes (or expires naturally if a worker crashes
mid-turn and never releases it).

## `outbound_deliveries`

The idempotency ledger. `idempotency_key` is unique; a repository
insert conflict on that key is how `DuplicateDeliveryError` gets
raised. Kept as a permanent log (not deleted after delivery) so a
delivered-twice investigation has a record to inspect.

## `user_facts`

Memory rows, one per extracted fact, with `category`
(`background`/`constraint`/`preference`/`goal`), a `confidence` score,
an optional `fact_embedding` for semantic recall, and `superseded_by`
— a self-referencing FK used to mark an older fact replaced by a
newer, contradicting one without deleting history. The partial index
`user_facts_user_id_idx ... where superseded_by is null` keeps the
"current facts for this user" query fast without a table scan over
superseded rows.

## `match_scores`

Persisted ranking output: one row per `(user_id, job_id)` pair the
ranking engine has scored (enforced by
`match_scores_user_job_unique`), storing each of the five signal
scores plus `combined_score`. This lets the chat layer reference a
previously shown match by id and lets operations query score
distributions without recomputing ranking on the fly.

## `ranking_weight_versions`

A small config table (added alongside `match_scores` in migration
0002) recording each named set of ranking weights and when it was
activated, with a `check` constraint enforcing the five weights sum to
1.0. Exists so a weight change can be attributed to a specific
rollout rather than silently drifting via an unlogged config edit.

## Migration order

1. `0001_initial.sql` — `users`, `jobs`, `ingest_checkpoints`,
   `conversations`, `messages`, `turn_leases`,
   `outbound_deliveries`, `user_facts`.
2. `0002_add_match_scores.sql` — `match_scores`,
   `ranking_weight_versions`.

Migrations are additive only: a later migration may add tables,
columns, or indexes, but should not drop or rename a column another
migration already shipped without a corresponding backfill migration
alongside it.
