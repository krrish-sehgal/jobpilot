-- 0002_add_match_scores.sql
-- Persisted ranking output: one row per (user, job) the ranking engine
-- has scored, so a chat reply can reference a previously shown match
-- and operations can query score distributions without recomputing.

begin;

create table match_scores (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete cascade,
    job_id uuid not null references jobs (id) on delete cascade,

    semantic_similarity numeric(5, 4) not null check (semantic_similarity between 0 and 1),
    recency_score numeric(5, 4) not null check (recency_score between 0 and 1),
    seniority_fit_score numeric(5, 4) not null check (seniority_fit_score between 0 and 1),
    location_fit_score numeric(5, 4) not null check (location_fit_score between 0 and 1),
    completeness_score numeric(5, 4) not null check (completeness_score between 0 and 1),
    combined_score numeric(5, 4) not null check (combined_score between 0 and 1),

    created_at timestamptz not null default now(),

    constraint match_scores_user_job_unique unique (user_id, job_id)
);

create index match_scores_user_id_combined_score_idx
    on match_scores (user_id, combined_score desc);
create index match_scores_job_id_idx on match_scores (job_id);

-- Ranking weight config, versioned so a weight change can be
-- attributed to a specific rollout instead of silently drifting.
create table ranking_weight_versions (
    id uuid primary key default gen_random_uuid(),
    label text not null unique,
    weight_semantic numeric(4, 3) not null,
    weight_recency numeric(4, 3) not null,
    weight_seniority_fit numeric(4, 3) not null,
    weight_location_fit numeric(4, 3) not null,
    weight_completeness numeric(4, 3) not null,
    activated_at timestamptz not null default now(),
    constraint ranking_weight_versions_sum_to_one check (
        abs(
            weight_semantic + weight_recency + weight_seniority_fit
            + weight_location_fit + weight_completeness - 1.0
        ) < 0.001
    )
);

insert into ranking_weight_versions (
    label, weight_semantic, weight_recency, weight_seniority_fit,
    weight_location_fit, weight_completeness
) values (
    'default-v1', 0.45, 0.15, 0.20, 0.10, 0.10
);

commit;
