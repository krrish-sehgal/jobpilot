# JobPilot

A personal hobby / learning project: a structural reference
implementation of what an "agentic" job-search chatbot looks like on
the inside — the agent loop, durable message handling, a scraping →
enrichment → search pipeline, and a matching idea worth explaining.

> **This code does not run.** Every module is intentionally stubbed —
> functions raise `NotImplementedError("demo only")`, return obviously
> fake data, or just `pass`. There are no real credentials, no real
> integrations, nothing to connect to. It exists purely as a
> structural reference for studying how the pieces of a system like
> this fit together, not as working software. Treat it like an
> annotated diagram that happens to be written in Python.

I put this together while learning how agentic systems and job-search
tooling are typically put together, and wanted a version I could point
at and say "this box calls that box" without any of the noise of a
real, running codebase (auth, retries, real API keys, deployment
config). If you're a student trying to understand this kind of
project, hopefully reading through `src/jobpilot/` top to bottom is a
reasonable way to get the shape of it.

## What's here

```
jobpilot/
  src/jobpilot/
    agent/        the agent loop: model picks a tool, result feeds back in
    chat/         inbound webhook, durable-turn orchestration, card rendering
    ingest/       scrapers -> object storage -> queue -> enrichment worker
    search/       embeddings, hybrid (semantic + filters) search, ranking
    db/           a Supabase client placeholder + a small invented schema
  docs/
    architecture.md   the diagrams and reasoning behind each piece
```

## The ideas, briefly

1. **Agentic loop.** The model doesn't just generate a reply — it
   picks a tool (search jobs, recall memory, fetch resume), looks at
   the result, and decides again, until it has enough to answer.
2. **Durable turns.** An inbound message gets written to the database
   *before* anything else happens to it, so a crash mid-conversation
   resumes instead of losing the message. A claim-and-lease mechanism
   on top of that stops two workers from both replying to the same one.
3. **Long-term memory.** A background step pulls durable facts about a
   user out of past conversations; later turns retrieve them by
   meaning, not by keyword.
4. **Ingestion by platform, not by company.** Scrapers target
   applicant tracking systems (the hiring software many companies
   share), so one scraper reaches every employer using that platform.
   Postings flow through object storage, then a queue, then a worker —
   the queue is what lets scraping and processing scale independently.
5. **Enrichment.** An LLM turns messy posting text into a strict
   record (role category, seniority, skills, location, pay, scam-risk
   flag) against a small taxonomy invented for this demo.
6. **The matching idea — the interesting bit.** Rather than embedding
   the job description itself, the model writes a short description of
   the *ideal candidate* for that job, with the company name and
   location stripped out. Job seekers describe themselves in roughly
   the same register, so person-description-to-person-description
   comparisons tend to match better than posting-to-resume ones. See
   `docs/architecture.md` for the full reasoning.
7. **Hybrid search.** Semantic similarity plus structured hard filters
   (years of experience, city, role type), combined and then ranked.
   Neither one alone is enough.

See [`docs/architecture.md`](docs/architecture.md) for two diagrams
(the agent loop, and the ingestion pipeline) and the reasoning behind
each of the points above.

## Layout, if you want to read the code directly

- `agent/loop.py`, `agent/tools.py`, `agent/prompts.py` — the loop
  itself, the tools it can call, and the (deliberately short, untuned)
  prompt strings.
- `chat/webhook.py` — receives an inbound message, persists it, returns.
- `chat/orchestrator.py` — the claim-and-lease pattern for picking up
  and processing a pending message safely.
- `chat/cards.py` — turns a job match into a small chat-friendly card.
- `ingest/scrapers/base.py` — the `BaseScraper` contract: one scraper
  per ATS.
- `ingest/scrapers/demo_ats.py` — one example scraper, returning a few
  hardcoded fake postings.
- `ingest/queue.py`, `ingest/worker.py` — the queue in between scraping
  and enrichment, and the worker that drains it.
- `ingest/enrich.py` — the LLM enrichment step and the invented
  taxonomy (6 role categories, 4 seniority bands).
- `search/embed.py`, `search/hybrid.py`, `search/ranking.py` —
  embeddings, hybrid search, and final ranking.
- `db/client.py`, `db/schema.sql` — a Supabase client placeholder and
  the handful of invented tables everything above assumes exist.

## Setup (for reading, not running)

`.env.example` and `requirements.txt` are included so the *shape* of a
real deployment's configuration is visible — which environment
variables it would need, which kind of libraries it would sit on top
of. There's nothing to actually install and run against; every
`OPENAI_API_KEY`-style value in `.env.example` is an obvious
placeholder.

## Future ideas

Things I might explore if I keep extending this as a learning project:

- More scrapers, for more applicant tracking systems.
- Resume tailoring for a specific job, once a match is found.
- Reducing search latency: pre-matching in the background before a
  user even asks, caching common queries, using a smaller/cheaper
  model just for tool-routing decisions, and letting independent tool
  calls run in parallel instead of one at a time.
