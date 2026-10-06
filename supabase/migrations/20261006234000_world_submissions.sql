-- Anonymous URL-only suggestions, protected behind the server-side Edge Function.
-- Public visitors have no direct table privileges.
create table if not exists public.world_submissions (
  world_id text primary key,
  world_url text not null,
  world_name text not null,
  world_author text not null,
  world_description text not null default '',
  world_tags jsonb not null default '[]'::jsonb,
  world_thumbnail text,
  status text not null default 'queued'
    check (status in ('queued','needs_review','approved','not_club')),
  first_submitted_at timestamptz not null default now(),
  last_submitted_at timestamptz not null default now(),
  constraint world_submissions_id_format check
    (world_id ~ '^wrld_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'),
  constraint world_submissions_tags_array check
    (jsonb_typeof(world_tags)='array'),
  constraint world_submissions_size check
    (length(world_description)<=1800 and length(world_name)<=120
     and length(world_author)<=120 and length(world_url)<=250)
);
create index if not exists world_submissions_queue_idx
  on public.world_submissions(status, first_submitted_at);

create table if not exists public.world_submission_attempts (
  id uuid primary key default gen_random_uuid(),
  ip_day_hash text not null,
  world_id text not null,
  created_at timestamptz not null default now(),
  constraint world_submission_attempts_hash check(length(ip_day_hash)=64),
  constraint world_submission_attempts_id_format check
    (world_id ~ '^wrld_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
);
create index if not exists world_submission_attempts_limit_idx
  on public.world_submission_attempts(ip_day_hash, created_at desc);

alter table public.world_submissions enable row level security;
alter table public.world_submission_attempts enable row level security;
revoke all on table public.world_submissions from public, anon, authenticated;
revoke all on table public.world_submission_attempts from public, anon, authenticated;
grant select, insert, update, delete on table public.world_submissions to service_role;
grant select, insert, update, delete on table public.world_submission_attempts to service_role;
comment on table public.world_submissions is
  'Only public VRChat World metadata, no user identity; private API table for moderated AI club submissions.';
comment on table public.world_submission_attempts is
  'Private short-lived salted IP-day hashes for abuse-rate enforcement, not exposed to public API.';
