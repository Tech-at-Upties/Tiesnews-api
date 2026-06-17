create extension if not exists postgis;
create extension if not exists pg_trgm;
create extension if not exists unaccent;

create table if not exists external_sources (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  connector_type text not null default 'rss',
  feed_url text not null unique,
  site_url text,
  detected_title text,
  detected_feed_type text,
  detected_language text,
  fetch_interval_minutes integer not null default 30,
  reliability_score numeric(4,3) not null default 0.700,
  enabled boolean not null default true,
  archived boolean not null default false,
  status text not null default 'active',
  category_scope jsonb,
  country_scope text,
  etag text,
  last_modified text,
  last_success_at timestamptz,
  last_failure_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists ingestion_jobs (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references external_sources(id),
  trigger_type text not null default 'manual',
  status text not null default 'queued',
  fetched_count integer not null default 0,
  duplicate_raw_count integer not null default 0,
  normalized_count integer not null default 0,
  event_candidate_count integer not null default 0,
  error_message text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists ingestion_logs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references ingestion_jobs(id),
  level text not null,
  message text not null,
  details jsonb,
  created_at timestamptz not null default now()
);

create table if not exists raw_fetched_items (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references external_sources(id),
  job_id uuid not null references ingestion_jobs(id),
  source_item_id text,
  source_url text,
  title text,
  raw_payload jsonb not null,
  content_hash text not null,
  published_at timestamptz,
  fetched_at timestamptz not null default now(),
  processing_status text not null default 'stored'
);

create table if not exists normalized_items (
  id uuid primary key default gen_random_uuid(),
  raw_item_id uuid not null references raw_fetched_items(id),
  source_id uuid not null references external_sources(id),
  canonical_url text,
  title text not null,
  summary text,
  body text,
  language text,
  image_url text,
  published_at timestamptz,
  category_hints jsonb,
  location_hints jsonb,
  extraction_status text not null default 'processed',
  created_at timestamptz not null default now()
);

create table if not exists normalized_item_locations (
  id uuid primary key default gen_random_uuid(),
  normalized_item_id uuid not null references normalized_items(id),
  name text not null,
  country_code text,
  latitude numeric(9,6),
  longitude numeric(9,6),
  geog geography(Point, 4326),
  confidence numeric(4,3),
  created_at timestamptz not null default now()
);

create table if not exists event_candidates (
  id uuid primary key default gen_random_uuid(),
  normalized_item_id uuid not null references normalized_items(id),
  source_id uuid not null references external_sources(id),
  title text not null,
  summary text,
  category_hints jsonb,
  location_hints jsonb,
  risk_hint text not null default 'unknown',
  publication_status text not null default 'api_visible',
  created_at timestamptz not null default now()
);

create table if not exists admin_api_keys (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  key_hash text not null unique,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  last_used_at timestamptz
);

create index if not exists idx_sources_connector_enabled on external_sources (connector_type, enabled);
create index if not exists idx_jobs_source_status_started on ingestion_jobs (source_id, status, started_at desc);
create unique index if not exists uq_raw_source_item_id on raw_fetched_items (source_id, source_item_id) where source_item_id is not null;
create unique index if not exists uq_raw_source_hash on raw_fetched_items (source_id, content_hash);
create index if not exists idx_normalized_source_published on normalized_items (source_id, published_at desc);
create index if not exists idx_normalized_status_published on normalized_items (extraction_status, published_at desc);
create index if not exists idx_normalized_title_trgm on normalized_items using gin (title gin_trgm_ops);
create index if not exists idx_item_locations_geog on normalized_item_locations using gist (geog);
create index if not exists idx_admin_api_keys_active on admin_api_keys (active);
