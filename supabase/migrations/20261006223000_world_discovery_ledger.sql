-- Private, provenance-first World discovery data.
-- No anonymous/authenticated API access: only trusted server jobs may upsert.
create table if not exists public.world_discovery_records (
  world_id text primary key,
  name text not null default '',
  author_hint text not null default '',
  first_seen_on date not null,
  last_seen_on date not null,
  status text not null check (status in ('published', 'pending', 'historical')),
  evidence jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  constraint world_discovery_valid_id check (
    world_id ~ '^wrld_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  ),
  constraint world_discovery_valid_dates check (last_seen_on >= first_seen_on),
  constraint world_discovery_evidence_array check (jsonb_typeof(evidence) = 'array')
);
create index if not exists world_discovery_records_status_idx
  on public.world_discovery_records (status, last_seen_on desc);

create table if not exists public.world_discovery_runs (
  observed_on date primary key,
  registered_worlds integer not null check (registered_worlds >= 0),
  pending_candidates integer not null check (pending_candidates >= 0),
  total_tracked_worlds integer not null check (total_tracked_worlds >= 0),
  historical_only integer not null check (historical_only >= 0),
  sources jsonb not null default '{}'::jsonb,
  source_health jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.world_discovery_records enable row level security;
alter table public.world_discovery_runs enable row level security;

revoke all on table public.world_discovery_records from public, anon, authenticated;
revoke all on table public.world_discovery_runs from public, anon, authenticated;
grant select, insert, update, delete on public.world_discovery_records to service_role;
grant select, insert, update, delete on public.world_discovery_runs to service_role;

comment on table public.world_discovery_records is
  'Private retained World IDs, source provenance, and pending/published status; no public API access.';
comment on table public.world_discovery_runs is
  'Private daily collection health metrics; no public API access.';
