-- 0001_initial.sql
-- Core schema: users, jobs, conversations/messages, turn leases,
-- outbound deliveries, and long-term memory facts.
--
-- Written for Postgres 15+ (Supabase). Uses `pgcrypto` for
-- `gen_random_uuid()` and `vector` (pgvector) for embedding columns.

begin;

create extension if not exists pgcrypto;
create extension if not exists vector;

-- ---------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------

create table users (
    id uuid primary key default gen_random_uuid(),
    external_id text not null unique,
    display_name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- jobs
-- ---------------------------------------------------------------------

create table jobs (
    id uuid primary key default gen_random_uuid(),
    source_platform text not null,
    source_listing_id text not null,
    content_hash text not null,
    title text not null,
    company text not null,
    description text not null,
    apply_url text not null,

    role_category text not null check (role_category in (
        'software_engineering', 'data_and_analytics', 'product_and_design',
        'sales_and_business_dev', 'marketing_and_growth',
        'operations_and_support', 'finance_and_legal', 'other'
    )),
    seniority_band text not null check (seniority_band in (
        'intern', 'entry', 'mid', 'senior', 'leadership'
    )),
    min_years_experience numeric(4, 1) not null check (min_years_experience >= 0),
    skills text[] not null default '{}',
    location_text text,
    location_tier text not null default 'unknown' check (location_tier in (
        'remote', 'hybrid', 'onsite', 'unknown'
    )),
    employment_type text not null default 'full_time' check (employment_type in (
        'full_time', 'part_time', 'contract', 'internship'
    )),
    compensation_currency char(3),
    compensation_min numeric(12, 2),
    compensation_max numeric(12, 2),
    compensation_period text default 'year',
    fraud_signal text not null default 'none' check (fraud_signal in (
        'none', 'suspicious', 'likely_scam'
    )),
    fraud_signal_reason text,

    candidate_profile_text text not null,
    candidate_profile_embedding vector(1536),

    posted_at timestamptz,
    enriched_at timestamptz not null default now(),
    created_at timestamptz not null default now(),

    constraint jobs_content_hash_unique unique (content_hash),
    constraint jobs_compensation_range_valid check (
        compensation_min is null or compensation_max is null
        or compensation_min <= compensation_max
    )
);

create index jobs_role_category_idx on jobs (role_category);
create index jobs_seniority_band_idx on jobs (seniority_band);
create index jobs_location_tier_idx on jobs (location_tier);
create index jobs_posted_at_idx on jobs (posted_at desc);
create index jobs_source_platform_idx on jobs (source_platform);
-- ivfflat index for approximate nearest-neighbour search on the
-- candidate-profile embedding; requires ANALYZE after bulk load.
create index jobs_candidate_profile_embedding_idx on jobs
    using ivfflat (candidate_profile_embedding vector_cosine_ops)
    with (lists = 100);

-- ---------------------------------------------------------------------
-- ingestion checkpoints
-- ---------------------------------------------------------------------

create table ingest_checkpoints (
    source_platform text primary key,
    cursor text,
    last_run_started_at timestamptz,
    last_run_completed_at timestamptz,
    postings_seen integer not null default 0,
    postings_new integer not null default 0,
    postings_duplicate integer not null default 0,
    updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- conversations & messages
-- ---------------------------------------------------------------------

create table conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete cascade,
    created_at timestamptz not null default now()
);

create table messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations (id) on delete cascade,
    user_id uuid not null references users (id) on delete cascade,
    direction text not null check (direction in ('inbound', 'outbound')),
    body text not null,
    status text not null default 'received' check (status in (
        'received', 'processing', 'processed', 'failed'
    )),
    created_at timestamptz not null default now()
);

create index messages_conversation_id_idx on messages (conversation_id, created_at);

-- claim-and-lease: at most one active lease per conversation
create table turn_leases (
    conversation_id uuid primary key references conversations (id) on delete cascade,
    worker_id text not null,
    claimed_at timestamptz not null,
    expires_at timestamptz not null
);

create index turn_leases_expires_at_idx on turn_leases (expires_at);

-- outbound idempotency ledger
create table outbound_deliveries (
    id uuid primary key default gen_random_uuid(),
    idempotency_key text not null unique,
    conversation_id uuid not null references conversations (id) on delete cascade,
    body text not null,
    delivered_at timestamptz
);

-- ---------------------------------------------------------------------
-- long-term memory
-- ---------------------------------------------------------------------

create table user_facts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete cascade,
    fact_text text not null,
    category text not null default 'general',
    confidence numeric(3, 2) not null default 0.8 check (confidence between 0 and 1),
    fact_embedding vector(1536),
    source_message_id uuid references messages (id) on delete set null,
    superseded_by uuid references user_facts (id) on delete set null,
    created_at timestamptz not null default now()
);

create index user_facts_user_id_idx on user_facts (user_id) where superseded_by is null;

commit;
