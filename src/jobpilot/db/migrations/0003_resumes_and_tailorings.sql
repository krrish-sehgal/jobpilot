-- 0003_resumes_and_tailorings.sql
-- Web channel: email sign-in, resumes, resume tailoring, saved jobs, and
-- idempotent browser messages.
--
-- Additive only. Every existing table keeps its columns and constraints;
-- new columns are nullable or carry defaults, so the webhook channel that
-- shipped in 0001 keeps working while this migration runs and after it.
-- Rollback is `drop table` for the new tables and `drop column` for the
-- new columns; no existing data is rewritten.

begin;

-- ---------------------------------------------------------------------
-- users: email sign-in
-- ---------------------------------------------------------------------

alter table users
    add column email text,
    add column seniority_band text check (seniority_band in (
        'intern', 'entry', 'mid', 'senior', 'leadership'
    )),
    add column preferred_location_tiers text[] not null default '{}';

-- Case-insensitive uniqueness, only for rows that have an email, so
-- webhook-only users (email is null) are unaffected.
create unique index users_email_unique on users (lower(email)) where email is not null;

-- ---------------------------------------------------------------------
-- auth_codes: one-time sign-in codes
-- ---------------------------------------------------------------------

create table auth_codes (
    id uuid primary key default gen_random_uuid(),
    email text not null,
    -- HMAC-SHA256(secret, email || code). The 6-digit space is tiny, so
    -- the key matters: a leaked table alone cannot be brute-forced.
    code_hash text not null,
    expires_at timestamptz not null,
    attempts integer not null default 0,
    consumed_at timestamptz,
    created_at timestamptz not null default now()
);

create index auth_codes_email_created_idx on auth_codes (email, created_at desc);

-- ---------------------------------------------------------------------
-- conversations: titles for the sidebar
-- ---------------------------------------------------------------------

alter table conversations
    add column title text not null default 'New conversation',
    add column updated_at timestamptz not null default now();

create index conversations_user_updated_idx on conversations (user_id, updated_at desc);

-- ---------------------------------------------------------------------
-- resumes
-- ---------------------------------------------------------------------

create table resumes (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete cascade,
    file_name text not null,
    storage_key text not null,
    status text not null default 'parsing' check (status in ('parsing', 'ready', 'failed')),
    failure_reason text,
    is_primary boolean not null default false,
    raw_text text,
    sections jsonb,
    uploaded_at timestamptz not null default now()
);

create index resumes_user_uploaded_idx on resumes (user_id, uploaded_at desc);
-- At most one primary resume per user, enforced by the database.
create unique index resumes_one_primary_per_user on resumes (user_id) where is_primary;

-- ---------------------------------------------------------------------
-- tailorings
-- ---------------------------------------------------------------------

create table tailorings (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete cascade,
    resume_id uuid not null references resumes (id) on delete cascade,
    -- null when the user pasted a job description instead of picking a job
    job_id uuid references jobs (id) on delete set null,
    job_description_text text,
    job_title text not null,
    company text,
    job_seniority_band text,
    status text not null default 'running' check (status in ('running', 'ready', 'failed')),
    failure_reason text,
    score_before numeric(5, 1) not null default 0 check (score_before between 0 and 100),
    score_after numeric(5, 1) not null default 0 check (score_after between 0 and 100),
    keywords jsonb not null default '[]',
    created_at timestamptz not null default now()
);

create index tailorings_user_created_idx on tailorings (user_id, created_at desc);

create table tailoring_suggestions (
    id uuid primary key default gen_random_uuid(),
    tailoring_id uuid not null references tailorings (id) on delete cascade,
    position integer not null,
    kind text not null check (kind in (
        'rewrite_bullet', 'rewrite_summary', 'add_skill', 'reorder_section'
    )),
    target_id text,
    section text not null check (section in ('summary', 'experience', 'projects', 'skills')),
    original text,
    proposed text not null,
    reason text not null default '',
    keywords_added text[] not null default '{}',
    decision text not null default 'pending' check (decision in (
        'pending', 'accepted', 'rejected'
    ))
);

create index tailoring_suggestions_tailoring_idx on tailoring_suggestions (tailoring_id, position);

-- ---------------------------------------------------------------------
-- saved jobs
-- ---------------------------------------------------------------------

create table saved_jobs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete cascade,
    job_id uuid not null references jobs (id) on delete cascade,
    created_at timestamptz not null default now(),
    constraint saved_jobs_user_job_unique unique (user_id, job_id)
);

create index saved_jobs_user_created_idx on saved_jobs (user_id, created_at desc);

-- ---------------------------------------------------------------------
-- messages: web channel columns
-- ---------------------------------------------------------------------

alter table messages
    add column client_message_id text,
    add column turn_id uuid,
    add column job_cards jsonb not null default '[]',
    add column tailoring_id uuid references tailorings (id) on delete set null;

-- Idempotent POSTs: the same browser-generated id in the same
-- conversation can only ever create one message. The unique index is the
-- backstop for two concurrent requests racing past the application check.
create unique index messages_client_message_id_unique
    on messages (conversation_id, client_message_id)
    where client_message_id is not null;

create index messages_turn_id_idx on messages (turn_id) where turn_id is not null;

commit;
