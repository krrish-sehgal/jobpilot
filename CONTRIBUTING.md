# Contributing to JobPilot

## Local setup

```bash
git clone https://github.com/krrish-sehgal/jobpilot.git
cd jobpilot
python -m venv .venv && source .venv/bin/activate
make install
cp .env.example .env   # fill in real values for anything you need to run live
```

## Development loop

```bash
make lint      # ruff check + format check
make format    # apply ruff formatting
make test      # pytest
make coverage  # pytest with coverage report
make run       # start the webhook service locally
```

Every pull request must pass `make lint` and `make test` (this is
also enforced by CI). Run `make format` before opening a PR rather
than hand-formatting.

## Project conventions

- **Layering.** `agent/`, `chat/`, `ingest/`, `search/`, `memory/` are
  service layers; they depend on `db/repositories/*` for persistence
  and `integrations/*` for external systems, never the other way
  around. A repository should never import from a service layer.
- **External boundaries stay behind an interface.** If you're adding
  a new external dependency (a new LLM provider, a new queue backend),
  add it to `integrations/` behind the existing protocol where one
  exists, with a real implementation and an in-memory fake, and wire
  the fake into the relevant tests. Do not let application code call
  a third-party SDK directly.
- **Domain models are the contract.** Any data crossing a layer
  boundary should be a `pydantic.BaseModel` from `jobpilot/models.py`,
  not a raw dict, so validation happens once at the boundary.
- **Exceptions.** Raise a subclass of `JobPilotError` (see
  `jobpilot/errors.py`) for any failure you want a caller to handle
  deliberately. Let genuinely unexpected exceptions propagate rather
  than catching `Exception` broadly.
- **Taxonomy changes.** The role/seniority/location taxonomy in
  `jobpilot/models.py` is referenced by the enrichment prompt
  (`jobpilot/ingest/prompts.py`), the database schema
  (`db/migrations/0001_initial.sql`), and the ranking engine. If you
  change it, update all three in the same PR, and add a new migration
  rather than editing an existing one.

## Tests

New logic (ranking, dedup, retry, chunking, validation, the agent
loop, the orchestrator) should ship with unit tests using the fakes in
`integrations/` — `FakeLLMClient`, `InMemoryDatabase`,
`InMemoryQueueBackend`, `InMemoryObjectStorage`. Tests should not
require network access or real credentials; if a test would need
either, it belongs behind a marker excluded from the default `pytest`
run, with a clear comment explaining why.

## Commit style

Commit messages describe the change in plain, specific language (e.g.
"Add checkpointing so scraper restarts resume mid-crawl", not "fix
stuff"). Keep unrelated changes in separate commits.
