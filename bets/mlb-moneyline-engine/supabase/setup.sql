create extension if not exists pgcrypto;

create table if not exists public.pregame_snapshots (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    event_id text,
    game_pk bigint,
    matchup text not null,
    commence_time timestamptz,
    lineups_confirmed boolean not null default false,
    payload jsonb not null
);

create index if not exists pregame_snapshots_created_at_idx
    on public.pregame_snapshots (created_at desc);

create index if not exists pregame_snapshots_game_pk_idx
    on public.pregame_snapshots (game_pk);

alter table public.pregame_snapshots enable row level security;

-- No public policies are created. The Render server uses the private service-role key.
