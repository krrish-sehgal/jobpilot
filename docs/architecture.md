# Architecture

## Overview

JobPilot has three pipelines that meet at the `jobs` table:

1. **Ingestion** — scrapers pull postings from applicant tracking
   systems, dedupe and checkpoint them, and hand them to an
   enrichment worker that turns raw text into a validated `JobRecord`.
2. **Search** — hybrid retrieval (structured filters + semantic
   similarity) and a weighted ranking engine turn a query into a
   ranked list of matches.
3. **Chat** — an inbound webhook durably records messages, a
   claim-and-lease orchestrator runs the agentic loop exactly once per
   turn, and an idempotent delivery ledger sends the reply.

```
                 ┌──────────────┐
 Talentflow ───▶ │              │
 Hirebridge ───▶ │  Scrapers    │──▶ object storage ──▶ queue ──▶ Enrichment ──▶ jobs table
 Recruitly  ───▶ │ (BaseScraper)│                                  (LLM call)      (+ pgvector)
 Stackroll  ───▶ │              │
                 └──────────────┘

 Webhook ──▶ messages table ──▶ Orchestrator (claim-and-lease) ──▶ Agent loop ──▶ Delivery ledger
                                                                        │
                                                              tools: search_jobs, recall_memory,
                                                              fetch_resume, get_job_details
                                                                        │
                                                                 Hybrid search + ranking
                                                                    (reads jobs table)
```

## Ingestion pipeline

Each scraper (`ingest/scrapers/*.py`) implements `BaseScraper`:
`platform_name` and `fetch_page(cursor)`. The base class owns rate
limiting via a token bucket so no subclass has to reimplement request
pacing. `ScraperRunner` (`ingest/worker.py`) drives a scraper to
completion, and for every page:

1. Checks each posting against `Deduplicator`, which hashes
   `(title, company, description)` — not `(platform, listing_id)` — so
   the same posting re-appearing under a new listing id, or mirrored
   on a second platform, is still recognized as a duplicate.
2. Writes new postings to object storage as the durable raw record.
3. Publishes them to the ingestion queue.
4. Advances the platform's checkpoint (`ingest/checkpoint.py`), so a
   crash mid-crawl resumes from the last committed cursor on restart
   rather than re-scraping from the beginning.

`EnrichmentWorker` drains the queue independently, at whatever rate
the LLM provider can sustain, decoupling a bursty scrape from a
steady-rate enrichment cost.

## Enrichment and the taxonomy

`ingest/enrich.py` sends the enrichment prompt
(`ingest/prompts.py:ENRICHMENT_SYSTEM_PROMPT`) with the cleaned
posting text and gets back JSON matching a fixed contract: role
category (one of 8), seniority band (one of 5, each mapped to a
year-of-experience range in `models.py:SENIORITY_YEAR_RANGES`),
minimum years of experience, skills, location tier, employment type,
compensation, and a fraud-signal check. `_build_job_record` validates
every enum field against the taxonomy and raises
`EnrichmentSchemaError` for anything outside it — a mismatch between
stated years and seniority band is deterministically corrected from
the years rather than trusted blindly, since years is a number and
the band is a label the model sometimes gets sloppy with.

## The matching idea: candidate-profile embedding

Most job search treats "search" as matching a query against the job
description. JobPilot embeds something else: as part of enrichment,
the LLM is asked to write a 3–5 sentence description of the *ideal
candidate* for the role — company name and location stripped out —
and that text, `candidate_profile_text`, is what actually gets
embedded and stored (`jobs.candidate_profile_embedding` in the
schema).

The reasoning: a job description is written in the voice of the
employer, listing requirements and selling points. A job seeker,
when they describe what they want or what they've done, writes in a
completely different register — first person, background-and-goals
framed, not requirements-framed. Embedding the job description and
comparing it against a job seeker's self-description compares two
different kinds of text; the similarity signal is noisier than it
needs to be. By having the LLM translate the job posting into the
*same register* a candidate would use to describe themselves —
"has 5+ years building backend systems in Python and Go, comfortable
owning a service end to end, drawn to ambiguous early-stage problems"
— both sides of the comparison are person-descriptions, and cosine
similarity between them is a much more direct signal of fit than
query-to-posting similarity.

This is why `search/embed.py:embed_candidate_profile` embeds
`job.candidate_profile_text`, never `job.description`, and why the
ideal-candidate prompt (`ingest/prompts.py:IDEAL_CANDIDATE_PROMPT`)
explicitly instructs the model to strip company and location and
avoid restating the job title.

## Search and ranking

`search/hybrid.py:hybrid_search` is the entry point: it applies hard
structured filters first (`SearchFilters` — role category, seniority
band, location tier, employment type, pay floor, fraud exclusion),
then computes semantic similarity only over what survives filtering,
then scores and ranks. Filtering before embedding comparison isn't
just a performance optimization — a semantically excellent match in
the wrong seniority band is still a wrong answer, and only a hard
filter guarantees it never surfaces.

`search/ranking.py:score_job` combines five signals with configurable
weights (default: 45% semantic similarity, 15% recency, 20% seniority
fit, 10% location fit, 10% posting completeness):

- **Semantic similarity** — cosine similarity between the query
  embedding and the job's candidate-profile embedding, mapped from
  [-1, 1] to [0, 1].
- **Recency** — exponential decay with a 14-day half-life from
  `posted_at`; a posting with no known post date scores a neutral 0.5
  rather than being penalized for missing data.
- **Seniority fit** — 1.0 for an exact band match, decaying linearly
  with ordinal distance between the job's band and the candidate's
  stated band.
- **Location fit** — 1.0 if the job's location tier is among the
  candidate's preferred tiers, 0.0 if not, 0.3 if the job's tier is
  itself unknown (can't confirm, shouldn't zero out).
- **Completeness** — the fraction of secondary fields (skills,
  compensation, location tier, post date, a substantial description)
  present, as a thin proxy for posting quality.

## Chat pipeline: durability, leasing, and idempotency

Three guarantees, each implemented independently so a failure in one
doesn't silently break another:

1. **Persist before processing.** `chat/webhook.py` writes the
   inbound message to the `messages` table before returning a 200.
   If the process crashes immediately after, the message is durable
   and gets picked up by whatever mechanism polls for
   `status = 'received'` messages.
2. **Claim-and-lease.** `chat/orchestrator.py:TurnOrchestrator` claims
   a time-boxed lease on the conversation (`turn_leases` table)
   before running the agent loop. A second worker's claim on the same
   conversation fails with `TurnLeaseConflictError` while the lease is
   live, which is what prevents two replies to one message. The lease
   is released in a `finally` block so a crash mid-turn still frees it
   once it expires, rather than deadlocking the conversation forever.
3. **Idempotent delivery.** `chat/ledger.py:DeliveryLedger` records
   every outbound send keyed by `f"{conversation_id}:{message_id}"`
   before it's considered sent. A retried orchestrator run after a
   crash (which reprocesses the same message and produces the same
   key) gets a duplicate-delivery no-op instead of sending the reply
   twice.

## The agent loop

`agent/loop.py:AgentLoop.run` is a bounded loop: on each turn it sends
the conversation plus tool schemas to the LLM, and either gets tool
calls (which it validates via `agent/registry.py:ToolRegistry`,
executes, and feeds the results back as the next message) or a final
text reply (loop ends). `agent_max_turns` bounds the number of
round-trips; on the final allowed turn, the system prompt is extended
to force an answer rather than another tool request, so the loop
always terminates with either a reply or a `TurnBudgetExceededError` —
it never spins.

## Memory

`memory/extraction.py:extract_facts` runs over a window of
conversation history and returns durable facts (background,
constraint, preference, goal) using the extraction prompt's explicit
distinction between "durable fact about the user" and "instruction or
in-the-moment statement." `memory/store.py:MemoryStore` embeds facts
at write time and retrieves by cosine similarity at read time
(`recall_memory`, one of the agent's four tools), so a query like
"individual contributor roles" can surface a stored fact like "wants
to stay hands-on technical" without keyword overlap.
