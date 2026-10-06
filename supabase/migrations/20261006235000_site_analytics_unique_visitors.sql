-- Daily, non-public deduplicated browser visits for estimated unique visitors.
-- These are browser pseudonyms, NOT verified people. Raw browser tokens never stored.
create table if not exists public.site_analytics_unique_visits (
  visitor_hash text not null
    check(visitor_hash ~ '^[0-9a-f]{64}$'),
  visit_day date not null,
  last_seen_at timestamptz not null default now(),
  primary key (visitor_hash, visit_day)
);
create index if not exists site_analytics_unique_visits_last_seen_idx
  on public.site_analytics_unique_visits(last_seen_at desc);
alter table public.site_analytics_unique_visits enable row level security;
revoke all on table public.site_analytics_unique_visits from public, anon, authenticated;
grant select, insert, update, delete on table public.site_analytics_unique_visits to service_role;
comment on table public.site_analytics_unique_visits is
 'Server-secret salted hashes of browser-generated random IDs, grouped by JST day, used solely for aggregate 1/7/30-day estimates. No IP or UA. Old rows deleted during tracking once older than 40 days.';
