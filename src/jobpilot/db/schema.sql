-- JobPilot — invented demo schema
--
-- A handful of simple tables that illustrate the shapes the rest of
-- the codebase assumes exist. This is not a migration meant to be run
-- against anything; it is here so a reader can see the data model
-- alongside the code that talks about it.

create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    chat_user_id text not null unique,   -- id assigned by the chat platform
    display_name text,
    years_experience numeric,
    created_at timestamptz not null default now()
);

-- Every inbound chat message, written here BEFORE any agent processing.
-- See chat/webhook.py (persist_inbound_message) and
-- chat/orchestrator.py (claim_next_turn) for how this table is used.
create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id),
    platform_message_id text not null unique,
    text text not null,
    status text not null default 'pending',   -- pending | claimed | complete
    claimed_by text,                          -- worker id holding the lease
    lease_expires_at timestamptz,
    reply_text text,
    received_at timestamptz not null default now()
);

-- Durable facts extracted about a user from past conversations.
-- See agent/tools.py (recall_memory).
create table if not exists user_memory_facts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id),
    fact_text text not null,
    confidence numeric not null default 0.5,
    extracted_from_message_id uuid references messages(id),
    created_at timestamptz not null default now()
);

-- Enriched job postings. See ingest/enrich.py for the taxonomy
-- (role_category, seniority_band) these columns are constrained to.
create table if not exists jobs (
    id uuid primary key default gen_random_uuid(),
    source_ats text not null,
    source_posting_id text not null,
    company_name text,
    title text,
    role_category text not null,
    seniority_band text not null,
    skills text[] default '{}',
    location text,
    pay_range text,
    scam_risk boolean not null default false,
    scam_risk_reason text,
    ideal_candidate_description text,   -- see docs/architecture.md
    posting_url text,
    created_at timestamptz not null default now(),
    unique (source_ats, source_posting_id)
);

-- Precomputed / logged matches between a user and a job, so a match
-- (and why it was made) can be looked back on later rather than only
-- existing transiently inside a search call.
create table if not exists job_matches (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id),
    job_id uuid not null references jobs(id),
    semantic_score numeric,
    rank_score numeric,
    matched_at timestamptz not null default now()
);
