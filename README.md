# GeoAtlas Backend Low Level Design

Project work history is maintained in [documentation.md](documentation.md). The runnable data-collection backend is in [backend/](backend/) and implementation notes are in [docs/GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md](docs/GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md).

## 1. Backend Overview

GeoAtlas is a production backend for monitoring geo-intelligence, crisis, and conflict events from automated external sources and human analyst workflows. The backend owns authentication, authorization, event ingestion, analyst review, event publication, map-ready geospatial APIs, dashboards, watchlists, notifications, and auditability.

Core responsibilities:

| Area | Responsibility |
| --- | --- |
| Authentication | Register users, authenticate credentials, issue JWT access tokens, rotate refresh tokens, revoke sessions, expose current-user context. |
| User and role management | Manage users, roles, permissions, account state, analyst/admin privileges, and superadmin-only controls. |
| Automatic data fetching | Fetch from configured RSS, news API, public dataset, government alert, NGO, and OSINT-style public sources on schedules. |
| GeoAtlas source collection | Provide a small internal interface for adding RSS/feed links, testing auto-detection, triggering ingestion, and previewing normalized output without building a public news frontend. |
| Source management | Store source endpoint, connector type, reliability score, fetch interval, rate limit, credentials reference, and status. |
| Raw data storage | Persist unmodified fetched payloads for traceability, replay, audits, and normalization debugging. |
| Data normalization | Convert source-specific payloads into a common normalized item format. |
| Event extraction | Extract title, summary, category, actors, location, dates, casualties, affected infrastructure, and source references. |
| Event deduplication | Compare normalized and extracted events against existing events and pending events. |
| Event management | Create, update, archive, verify, tag, source-link, and publish events. |
| Risk scoring | Suggest risk level using rule-based scoring plus confidence inputs from extraction. |
| Verification workflow | Route AI or connector-generated events into review, then require analyst/admin approval before publication. |
| Watchlists | Let users follow countries, regions, categories, keywords, actors, or individual events. |
| Intel clusters | Group related events into operational intelligence clusters. |
| Dashboard statistics | Provide aggregate counts, time series, high-risk alerts, ingestion health, and verification statistics. |
| Moderation | Support analyst/admin edits, approvals, rejections, merge decisions, and duplicate resolution. |
| AI assistance | Generate suggestions only: summaries, categories, locations, risk, timelines, duplicate likelihood, and confidence. |
| Map support | Store event coordinates, country/region metadata, bounding-box queries, and map marker payloads using Supabase Postgres + PostGIS. |
| Public standalone API | Expose versioned read-only output endpoints for normalized items, extracted event candidates, approved events, exports, OpenAPI docs, and health checks. |
| Notifications | Notify users about watchlist matches, high-risk events, review assignments, and ingestion failures. |
| Audit logging | Record immutable security, source, ingestion, review, verification, and event mutation activity. |
| Scheduled jobs | Register, lock, run, retry, and observe recurring source ingestion jobs. |

## 2. System Architecture

The backend uses layered FastAPI architecture with clear separation between request handling, business logic, persistence, ingestion, source-specific connectors, and background execution.

```text
Clients
  |-- Web app
  |-- Admin console
  |-- Analyst console
  |-- Internal scripts
        |
        v
FastAPI API Layer
  |-- Auth middleware
  |-- RBAC dependency checks
  |-- Request validation
  |-- Response serialization
        |
        v
Service Layer
  |-- AuthService
  |-- EventService
  |-- IngestionService
  |-- ReviewQueueService
  |-- RiskScoringService
  |-- AIService
  |-- DashboardService
        |
        v
Repository Layer
  |-- SQLAlchemy repositories
  |-- Transaction boundaries
  |-- Query optimization
        |
        v
Database Layer
  |-- Supabase Postgres + PostGIS
  |-- Alembic migrations
  |-- Numeric lat/lon initially
  |-- PostGIS-compatible model for final geospatial expansion
        |
        +-------------------------------+
        |                               |
        v                               v
Redis Cache / Coordination       Logging / Monitoring
  |-- Rate counters              |-- App logs
  |-- Job locks                  |-- Ingestion logs
  |-- Feed cache                 |-- Audit logs
  |-- Dashboard cache            |-- Metrics
```

Final ingestion flow:

```text
External Sources
  -> Source Connectors
  -> Raw Data Store
  -> Normalization
  -> AI/Event Extraction
  -> Deduplication
  -> Risk Scoring
  -> Analyst/Admin Review
  -> Published Events
  -> Feed/Map/Dashboard/Watchlist APIs
```

Architecture layers:

| Layer | Purpose |
| --- | --- |
| API layer | FastAPI routers, dependencies, validation, auth checks, pagination, filtering, and response models. |
| Service layer | Business workflows, transaction orchestration, permissions-sensitive decisions, and domain rules. |
| Repository layer | SQLAlchemy queries, inserts, updates, row locking, relationship loading, and persistence concerns. |
| Database layer | PostgreSQL tables, indexes, constraints, migrations, and geospatial-ready schema. |
| Data ingestion layer | Job orchestration, raw item persistence, normalization, extraction, deduplication, scoring, and review queue insertion. |
| Source connector layer | Source-specific fetchers with retry, timeout, auth, rate limit, and response parsing rules. |
| Normalization layer | Converts heterogeneous payloads into common normalized records. |
| Deduplication layer | Calculates candidate matches against raw items, normalized items, pending events, and published events. |
| Background scheduler layer | Runs recurring jobs, prevents concurrent duplicate runs, tracks status, and enables manual triggers. |
| AI integration layer | Calls AI providers through controlled service methods and stores suggestions for review. |
| Cache layer | Redis-backed cache for feeds, dashboards, map aggregations, rate limits, and job locks. |
| Auth layer | Password hashing, JWT verification, refresh token rotation, RBAC, and permission checks. |
| Logging and monitoring layer | Structured application logs, ingestion logs, audit logs, metrics, and alert hooks. |

## 3. Backend Folder Structure

```text
geo-atlas/
  backend/
    app/
      main.py
      config.py
      database.py
      models.py
      schemas.py
      services.py
      feed_utils.py
      admin_keys.py
    db/
      geoatlas_data_collection_schema.sql
    scripts/
      generate_admin_key.py
    static/
      index.html
      styles.css
      app.js
    requirements.txt
    .env.example
  docs/
    GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md
  documentation.md
  HLD.md
  README.md
```

Folder responsibilities:

| Folder | Responsibility |
| --- | --- |
| `backend/app/main.py` | Creates FastAPI app, registers routes, serves the source console, and exposes health checks. |
| `backend/app/admin_keys.py` | Generates, hashes, stores, and validates database-backed admin API keys. |
| `backend/app/feed_utils.py` | RSS/Atom fetching, URL safety, feed discovery, parsing, and simple extraction helpers. |
| `backend/app/models.py` | SQLAlchemy ORM models and relationships for the current data-collection slice. |
| `backend/app/schemas.py` | Pydantic request/response DTOs. |
| `backend/app/services.py` | Source detection, source creation, ingestion, normalization, and event candidate workflows. |
| `backend/db/` | Supabase Postgres + PostGIS schema SQL. |
| `backend/scripts/` | Operational scripts such as admin key generation. |
| `backend/static/` | Internal GeoAtlas Source Console UI. |
| `docs/` | Implementation notes and supporting documentation. |

## 4. Automatic Data Fetching Design

Automatic fetching is a core backend capability. Source configuration drives scheduler registration, connector selection, rate limiting, retry behavior, and review routing.

### GeoAtlas Source Collection Module

GeoAtlas Data Collection is the first standalone data-collection slice of GeoAtlas. It lets an internal user add RSS or Atom feed links from a small frontend, while the backend performs feed detection, source validation, content extraction, normalization, geospatial hinting, and public API output.

This module deliberately does not require a public news-display frontend. The frontend only manages source addition and operational visibility. Consumers get output through JSON APIs, export endpoints, and OpenAPI documentation.

```text
Internal GeoAtlas Feed UI
  -> Add RSS/Atom URL
  -> Backend validates URL and blocks unsafe/private networks
  -> Backend detects feed type, title, site URL, language, favicon, and update cadence
  -> Source is saved in Supabase Postgres
  -> Scheduler or manual trigger fetches entries
  -> Raw payloads are stored unchanged
  -> Article content is extracted and normalized
  -> Locations/categories/entities/event candidates are detected
  -> Output is exposed through public API endpoints
```

Frontend scope:

| Screen | Controls | Backend APIs |
| --- | --- | --- |
| Add feed | URL input, source name override, reliability score, interval, enabled toggle | `POST /api/v1/sources/detect`, `POST /api/v1/sources/rss` |
| Source list | Status, last success/failure, enabled toggle, delete/archive action | `GET /api/v1/sources`, `PATCH /api/v1/sources/{source_id}` |
| Source detail | Detected metadata, recent jobs, recent normalized items, latest errors | `GET /api/v1/sources/{source_id}`, `GET /api/v1/ingestion/jobs` |
| Manual run | Trigger button, progress state, counters | `POST /api/v1/sources/{source_id}/ingest`, `GET /api/v1/ingestion/jobs/{job_id}` |
| Output preview | Table/JSON view for normalized items and candidate events | `GET /api/v1/public/items`, `GET /api/v1/public/events` |

Public output surfaces:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/public/items` | Paginated normalized feed items with source, canonical URL, title, summary, language, published time, extraction status, and geospatial hints. |
| `GET /api/v1/public/items/{item_id}` | Single normalized item with raw-source references and extraction metadata. |
| `GET /api/v1/public/events` | API-visible event candidates or approved events, filterable by country, category, date, risk, and bbox. |
| `GET /api/v1/public/export.json` | Download filtered items/events as JSON for downstream consumers. |
| `GET /api/v1/public/sources` | Public-safe source catalog without secrets or internal error details. |
| `GET /openapi.json` | Machine-readable public API contract for standalone integration. |

Standalone API requirements:

| Requirement | Design |
| --- | --- |
| Independent deployability | Keep data collection routes, schemas, migrations, workers, and environment variables independent enough to run as a separate FastAPI service. |
| Supabase boundary | API uses server-side Supabase Postgres credentials; browser clients never receive service-role keys. |
| Public read safety | Public endpoints return sanitized fields only and never expose raw private metadata, credentials, stack traces, or admin-only notes. |
| Output without frontend | Every collected item should be retrievable by API, export, or direct database read model. |
| API documentation | OpenAPI docs must show examples for adding feeds, triggering ingestion, polling jobs, and reading output. |
| Rate limits | Public endpoints use IP/API-key limits; admin ingestion endpoints require auth and stricter limits. |

### Source Configuration

Sources are stored in `external_sources`.

Key source fields:

| Field | Purpose |
| --- | --- |
| `connector_type` | `rss`, `news_api`, `dataset`, `government_alert`, `manual`. |
| `base_url` | Public endpoint, feed URL, API URL, or dataset location. |
| `auth_type` | `none`, `api_key`, `bearer`, `basic`, `signed_url`. |
| `secret_ref` | Environment or secret-manager key name, not the secret value. |
| `fetch_interval_minutes` | Recurring schedule interval. |
| `rate_limit_per_hour` | Source-specific request ceiling. |
| `reliability_score` | Decimal score from `0.00` to `1.00`. |
| `enabled` | Source can be paused without deletion. |
| `country_scope` | Optional country or region scope. |
| `category_scope` | Optional categories expected from the source. |
| `detected_title` | Feed title detected from RSS/Atom metadata. |
| `detected_site_url` | Canonical website URL linked from the feed. |
| `detected_feed_type` | `rss`, `atom`, or compatible feed format. |
| `detected_language` | Feed-level language hint when available. |
| `etag` | Last feed ETag for conditional requests. |
| `last_modified` | Last feed `Last-Modified` value for conditional requests. |

### Connector Types

| Connector | Responsibilities |
| --- | --- |
| `RSSConnector` | Fetch RSS/Atom feeds, parse entries, respect ETag/Last-Modified, compute entry fingerprints. |
| `NewsAPIConnector` | Call news APIs with API key references, handle pagination, normalize provider errors, respect quotas. |
| `DatasetConnector` | Download or query CSV, JSON, or API datasets, detect file version changes, batch process records. |
| `GovernmentAlertConnector` | Fetch official advisories, alerts, bulletins, and emergency messages with high source reliability defaults. |
| `ManualConnector` | Accept analyst/admin-entered raw text or links as raw fetched items with explicit provenance. |

### Retry and Failure Handling

| Failure | Handling |
| --- | --- |
| Timeout | Retry with exponential backoff, then mark job partially failed. |
| HTTP 429 | Respect `Retry-After`, pause source until allowed, log rate-limit event. |
| HTTP 5xx | Retry up to configured limit and preserve failed response metadata. |
| Invalid payload | Store ingestion log with parser error; do not create normalized item. |
| Auth failure | Disable source after threshold and notify admins. |
| Network failure | Retry later; job remains failed but source stays enabled unless repeated threshold is exceeded. |

Duplicate raw entries are avoided with a `content_hash` and `source_item_id` unique strategy:

```text
unique(source_id, source_item_id) when source_item_id is present
unique(source_id, content_hash) for sources without stable item ids
```

Ingestion logs record job start, connector request metadata, status changes, retry count, fetched count, duplicate raw count, normalized count, pending-event count, failures, and duration.

### RSS/Atom Auto-Detection

The feed-add flow supports both direct feed URLs and website URLs.

Detection order:

| Step | Behavior |
| --- | --- |
| 1. Validate URL | Accept only `http` and `https`; reject localhost, private IPs, link-local, metadata services, and unsupported schemes. |
| 2. Fetch headers | Use short timeout, size limits, redirect validation, and content-type checks. |
| 3. Parse direct feed | If response is RSS/Atom/XML, parse channel/feed metadata and sample entries. |
| 4. Discover feed links | If response is HTML, inspect `<link rel="alternate" type="application/rss+xml">` and Atom equivalents. |
| 5. Score candidates | Prefer valid feeds with recent entries, stable GUIDs, canonical links, and parseable published dates. |
| 6. Return preview | Show detected title, site URL, feed URL, language, latest item titles, update cadence, and warnings. |
| 7. Save source | Store selected feed URL and detection metadata only after user confirmation. |

Content extraction:

| Field | Detection |
| --- | --- |
| Canonical URL | Entry link, canonical HTML tag, or feed item URL. |
| Title | Feed entry title with HTML stripped and whitespace normalized. |
| Body | Entry content, summary, or fetched article body using a readability-style extractor. |
| Published time | Entry published/updated timestamp normalized to UTC. |
| Language | Feed language, article metadata, or text-language detection. |
| Image/media | Feed enclosures, Open Graph image, or article image metadata. |
| Location hints | Place names, country names, coordinates in metadata, and geocoding candidates. |
| Category hints | Feed categories, tags, keywords, and classifier output. |

## 5. Data Ingestion Pipeline

Pipeline stages:

| Stage | Detail |
| --- | --- |
| 1. Fetch raw data | Scheduler or manual trigger loads source config, acquires job lock, calls connector. |
| 2. Store raw fetched item | Persist original payload, source metadata, hash, fetch timestamp, and job id. |
| 3. Normalize fields | Convert source-specific fields into title, body, url, published_at, country hints, author, language, and media references. |
| 4. Extract event details | Extract incident title, category, actors, casualty hints, affected systems, summary, and event date. |
| 5. Extract location | Resolve country, admin area, place name, latitude, longitude, precision, and confidence. |
| 6. Extract category | Assign one or more categories such as war, border dispute, protest, terrorism, cyber attack, crisis, disaster, or instability. |
| 7. Generate AI summary | AI may summarize and structure text; failures do not block raw storage. |
| 8. Detect duplicate event | Compare fingerprint, title similarity, source URL, location proximity, category, and time window. |
| 9. Suggest risk level | Rule-based scorer suggests low, medium, or high with score breakdown. |
| 10. Suggest verification status | Verification service suggests status using source reliability and corroboration. |
| 11. Save pending event | Store event as `pending_review`, never directly published by AI. |
| 12. Send to review queue | Create assigned or unassigned queue item for analysts/admins. |
| 13. Publish after review | Analyst/admin approves, edits, merges, rejects, or marks false/disputed. |

AI is advisory only. It cannot publish, verify, delete, or archive events. Every AI output is stored in `ai_suggestions` and tied to the raw item, normalized item, event, and approving/rejecting user where applicable.

## 6. Database Design

Use Supabase Postgres with Alembic migrations and PostGIS enabled. Store `latitude` and `longitude` as `NUMERIC(9,6)` for simple projections and keep a `GEOGRAPHY(Point, 4326)` column on location tables for distance, bounding-box, and map queries.

Required Supabase extensions:

```sql
create extension if not exists postgis;
create extension if not exists pg_trgm;
create extension if not exists unaccent;
```

Supabase security boundary:

| Concern | Design |
| --- | --- |
| API database access | FastAPI uses server-side database credentials or Supabase service role in backend-only environment variables. |
| Browser access | The GeoAtlas source console calls FastAPI, not Supabase directly, unless a later read-only anon policy is deliberately added. |
| Public reads | Prefer FastAPI public endpoints for filtering, sanitization, rate limiting, and stable response contracts. |
| Row-level security | Enable RLS for tables exposed directly through Supabase; keep write tables service-only by default. |

### Common Columns

Most mutable tables include:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `UUID` | Primary key. |
| `created_at` | `TIMESTAMPTZ` | Default `now()`. |
| `updated_at` | `TIMESTAMPTZ` | Updated on mutation. |
| `deleted_at` | `TIMESTAMPTZ NULL` | Soft delete where applicable. |

### Tables

#### `users`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `email` | `VARCHAR(255)` | Unique, not null |
| `username` | `VARCHAR(80)` | Unique, not null |
| `password_hash` | `TEXT` | Not null |
| `full_name` | `VARCHAR(160)` | Not null |
| `status` | `VARCHAR(30)` | `active`, `disabled`, `pending` |
| `last_login_at` | `TIMESTAMPTZ` | Nullable |
| `refresh_token_hash` | `TEXT` | Nullable, rotated |
| `refresh_token_expires_at` | `TIMESTAMPTZ` | Nullable |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | Not null |

Indexes: unique `email`, unique `username`, index `status`.

#### `roles`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `name` | `VARCHAR(50)` | Unique, not null |
| `description` | `TEXT` | Nullable |

Seed roles: `guest`, `user`, `analyst`, `admin`, `superadmin`.

#### `permissions`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `code` | `VARCHAR(120)` | Unique, not null |
| `description` | `TEXT` | Nullable |

#### `role_permissions`

| Field | Type | Constraints |
| --- | --- | --- |
| `role_id` | `UUID` | FK -> `roles.id` |
| `permission_id` | `UUID` | FK -> `permissions.id` |

Primary key: `(role_id, permission_id)`.

#### `user_roles`

| Field | Type | Constraints |
| --- | --- | --- |
| `user_id` | `UUID` | FK -> `users.id` |
| `role_id` | `UUID` | FK -> `roles.id` |
| `assigned_by` | `UUID` | FK -> `users.id`, nullable |
| `assigned_at` | `TIMESTAMPTZ` | Not null |

Primary key: `(user_id, role_id)`.

#### `external_sources`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `name` | `VARCHAR(160)` | Unique, not null |
| `connector_type` | `VARCHAR(40)` | Not null |
| `base_url` | `TEXT` | Not null for external connectors |
| `auth_type` | `VARCHAR(40)` | Default `none` |
| `secret_ref` | `VARCHAR(160)` | Nullable |
| `fetch_interval_minutes` | `INTEGER` | Check `>= 5` |
| `rate_limit_per_hour` | `INTEGER` | Nullable |
| `reliability_score` | `NUMERIC(4,3)` | Check `0 <= score <= 1` |
| `enabled` | `BOOLEAN` | Default true |
| `country_scope` | `VARCHAR(120)` | Nullable |
| `category_scope` | `JSONB` | Nullable |
| `last_success_at` | `TIMESTAMPTZ` | Nullable |
| `last_failure_at` | `TIMESTAMPTZ` | Nullable |
| `created_by` | `UUID` | FK -> `users.id` |

Indexes: `connector_type`, `enabled`, `reliability_score`, `last_success_at`.

#### `ingestion_jobs`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `source_id` | `UUID` | FK -> `external_sources.id` |
| `trigger_type` | `VARCHAR(30)` | `scheduled`, `manual`, `retry` |
| `status` | `VARCHAR(30)` | `queued`, `running`, `success`, `partial_failure`, `failed`, `cancelled` |
| `started_at` | `TIMESTAMPTZ` | Nullable |
| `finished_at` | `TIMESTAMPTZ` | Nullable |
| `fetched_count` | `INTEGER` | Default 0 |
| `duplicate_raw_count` | `INTEGER` | Default 0 |
| `normalized_count` | `INTEGER` | Default 0 |
| `pending_event_count` | `INTEGER` | Default 0 |
| `error_message` | `TEXT` | Nullable |
| `triggered_by` | `UUID` | FK -> `users.id`, nullable |

Indexes: `source_id`, `status`, `started_at DESC`.

#### `ingestion_logs`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `job_id` | `UUID` | FK -> `ingestion_jobs.id` |
| `source_id` | `UUID` | FK -> `external_sources.id` |
| `level` | `VARCHAR(20)` | `info`, `warning`, `error` |
| `event_type` | `VARCHAR(80)` | Not null |
| `message` | `TEXT` | Not null |
| `metadata` | `JSONB` | Nullable |
| `created_at` | `TIMESTAMPTZ` | Not null |

Indexes: `job_id`, `source_id`, `(level, created_at DESC)`.

#### `raw_fetched_items`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `source_id` | `UUID` | FK -> `external_sources.id` |
| `job_id` | `UUID` | FK -> `ingestion_jobs.id` |
| `source_item_id` | `VARCHAR(255)` | Nullable |
| `source_url` | `TEXT` | Nullable |
| `title` | `TEXT` | Nullable |
| `raw_payload` | `JSONB` | Not null |
| `raw_text` | `TEXT` | Nullable |
| `content_hash` | `CHAR(64)` | Not null |
| `published_at` | `TIMESTAMPTZ` | Nullable |
| `fetched_at` | `TIMESTAMPTZ` | Not null |
| `processing_status` | `VARCHAR(40)` | `new`, `normalized`, `failed`, `ignored` |

Indexes: `source_id`, `job_id`, `content_hash`, `published_at DESC`. Constraints: unique `(source_id, source_item_id)` where `source_item_id IS NOT NULL`; unique `(source_id, content_hash)`.

#### `normalized_items`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `raw_item_id` | `UUID` | Unique FK -> `raw_fetched_items.id` |
| `normalized_title` | `TEXT` | Not null |
| `normalized_body` | `TEXT` | Not null |
| `language` | `VARCHAR(20)` | Nullable |
| `country_hint` | `VARCHAR(120)` | Nullable |
| `category_hint` | `VARCHAR(80)` | Nullable |
| `event_date_hint` | `TIMESTAMPTZ` | Nullable |
| `entities` | `JSONB` | Nullable |
| `normalization_version` | `VARCHAR(40)` | Not null |
| `status` | `VARCHAR(30)` | `ready`, `failed`, `ignored` |

Indexes: `raw_item_id`, `country_hint`, `category_hint`, `event_date_hint`.

#### `events`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `title` | `VARCHAR(300)` | Not null |
| `summary` | `TEXT` | Not null |
| `description` | `TEXT` | Nullable |
| `category_id` | `UUID` | FK -> `event_categories.id` |
| `risk_level` | `VARCHAR(20)` | `low`, `medium`, `high` |
| `risk_score` | `NUMERIC(5,2)` | Check `0 <= score <= 100` |
| `verification_status` | `VARCHAR(30)` | `unverified`, `developing`, `verified`, `disputed`, `false` |
| `publication_status` | `VARCHAR(30)` | `pending_review`, `published`, `rejected`, `archived` |
| `event_date` | `TIMESTAMPTZ` | Not null |
| `first_seen_at` | `TIMESTAMPTZ` | Not null |
| `last_updated_at` | `TIMESTAMPTZ` | Not null |
| `created_from_normalized_item_id` | `UUID` | FK -> `normalized_items.id`, nullable |
| `created_by` | `UUID` | FK -> `users.id`, nullable |
| `published_by` | `UUID` | FK -> `users.id`, nullable |
| `published_at` | `TIMESTAMPTZ` | Nullable |
| `archived_at` | `TIMESTAMPTZ` | Nullable |

Indexes: `publication_status`, `risk_level`, `verification_status`, `event_date DESC`, `category_id`, full-text index on `title` and `summary`.

#### `event_sources`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `event_id` | `UUID` | FK -> `events.id` |
| `source_id` | `UUID` | FK -> `external_sources.id` |
| `raw_item_id` | `UUID` | FK -> `raw_fetched_items.id`, nullable |
| `url` | `TEXT` | Nullable |
| `source_title` | `TEXT` | Nullable |
| `reliability_snapshot` | `NUMERIC(4,3)` | Not null |
| `linked_at` | `TIMESTAMPTZ` | Not null |

Indexes: `event_id`, `source_id`; unique `(event_id, source_id, raw_item_id)`.

#### `event_categories`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `name` | `VARCHAR(100)` | Unique, not null |
| `slug` | `VARCHAR(100)` | Unique, not null |
| `description` | `TEXT` | Nullable |

Seed categories include war, border_dispute, protest, terrorism, cyber_attack, humanitarian_crisis, natural_disaster, political_instability.

#### `event_tags`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `event_id` | `UUID` | FK -> `events.id` |
| `tag` | `VARCHAR(80)` | Not null |

Indexes: `event_id`, `tag`; unique `(event_id, tag)`.

#### `event_timelines`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `event_id` | `UUID` | FK -> `events.id` |
| `occurred_at` | `TIMESTAMPTZ` | Not null |
| `title` | `VARCHAR(240)` | Not null |
| `description` | `TEXT` | Nullable |
| `source_id` | `UUID` | FK -> `external_sources.id`, nullable |
| `created_by` | `UUID` | FK -> `users.id`, nullable |

Indexes: `(event_id, occurred_at DESC)`.

#### `event_locations`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `event_id` | `UUID` | FK -> `events.id` |
| `country_code` | `CHAR(2)` | Nullable |
| `country_name` | `VARCHAR(120)` | Not null |
| `admin_area` | `VARCHAR(160)` | Nullable |
| `place_name` | `VARCHAR(200)` | Nullable |
| `latitude` | `NUMERIC(9,6)` | Nullable |
| `longitude` | `NUMERIC(9,6)` | Nullable |
| `location_precision` | `VARCHAR(30)` | `country`, `region`, `city`, `exact`, `unknown` |
| `confidence` | `NUMERIC(4,3)` | Check `0 <= confidence <= 1` |
| `geom` | `GEOGRAPHY(Point, 4326)` | Optional final deployment PostGIS column |

Indexes: `event_id`, `country_code`, `(latitude, longitude)`, PostGIS GiST index on `geom` when enabled.

#### `watchlists`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `user_id` | `UUID` | FK -> `users.id` |
| `name` | `VARCHAR(120)` | Not null |
| `description` | `TEXT` | Nullable |
| `is_active` | `BOOLEAN` | Default true |

Indexes: `user_id`; unique `(user_id, name)`.

#### `watchlist_items`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `watchlist_id` | `UUID` | FK -> `watchlists.id` |
| `item_type` | `VARCHAR(40)` | `country`, `category`, `keyword`, `actor`, `event` |
| `value` | `VARCHAR(240)` | Not null |

Indexes: `watchlist_id`, `(item_type, value)`.

#### `intel_clusters`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `name` | `VARCHAR(180)` | Not null |
| `description` | `TEXT` | Nullable |
| `status` | `VARCHAR(30)` | `active`, `closed`, `archived` |
| `risk_level` | `VARCHAR(20)` | Nullable |
| `created_by` | `UUID` | FK -> `users.id` |

Indexes: `status`, `risk_level`.

#### `cluster_events`

| Field | Type | Constraints |
| --- | --- | --- |
| `cluster_id` | `UUID` | FK -> `intel_clusters.id` |
| `event_id` | `UUID` | FK -> `events.id` |
| `added_by` | `UUID` | FK -> `users.id` |
| `added_at` | `TIMESTAMPTZ` | Not null |

Primary key: `(cluster_id, event_id)`.

#### `ai_suggestions`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `raw_item_id` | `UUID` | FK -> `raw_fetched_items.id`, nullable |
| `normalized_item_id` | `UUID` | FK -> `normalized_items.id`, nullable |
| `event_id` | `UUID` | FK -> `events.id`, nullable |
| `suggestion_type` | `VARCHAR(60)` | `summary`, `category`, `risk`, `verification`, `location`, `timeline`, `duplicate`, `entity` |
| `input_hash` | `CHAR(64)` | Not null |
| `suggested_value` | `JSONB` | Not null |
| `confidence` | `NUMERIC(4,3)` | Nullable |
| `model_name` | `VARCHAR(120)` | Not null |
| `prompt_version` | `VARCHAR(40)` | Not null |
| `status` | `VARCHAR(30)` | `pending`, `approved`, `rejected`, `superseded` |
| `reviewed_by` | `UUID` | FK -> `users.id`, nullable |
| `reviewed_at` | `TIMESTAMPTZ` | Nullable |

Indexes: `event_id`, `suggestion_type`, `status`, `created_at DESC`.

#### `duplicate_candidates`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `source_event_id` | `UUID` | FK -> `events.id` |
| `candidate_event_id` | `UUID` | FK -> `events.id` |
| `similarity_score` | `NUMERIC(5,2)` | Check `0 <= score <= 100` |
| `reason` | `JSONB` | Not null |
| `status` | `VARCHAR(30)` | `pending`, `merged`, `rejected` |
| `resolved_by` | `UUID` | FK -> `users.id`, nullable |
| `resolved_at` | `TIMESTAMPTZ` | Nullable |

Indexes: `source_event_id`, `candidate_event_id`, `status`; unique `(source_event_id, candidate_event_id)`.

#### `review_queue`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `event_id` | `UUID` | FK -> `events.id` |
| `queue_type` | `VARCHAR(40)` | `new_event`, `duplicate`, `verification`, `risk_change`, `ai_suggestion` |
| `priority` | `INTEGER` | 1 to 5 |
| `status` | `VARCHAR(30)` | `pending`, `in_review`, `approved`, `rejected`, `merged` |
| `assigned_to` | `UUID` | FK -> `users.id`, nullable |
| `created_reason` | `TEXT` | Nullable |
| `decision_notes` | `TEXT` | Nullable |
| `resolved_by` | `UUID` | FK -> `users.id`, nullable |
| `resolved_at` | `TIMESTAMPTZ` | Nullable |

Indexes: `status`, `priority DESC`, `assigned_to`, `event_id`.

#### `audit_logs`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `actor_user_id` | `UUID` | FK -> `users.id`, nullable |
| `action` | `VARCHAR(100)` | Not null |
| `entity_type` | `VARCHAR(80)` | Not null |
| `entity_id` | `UUID` | Nullable |
| `before_value` | `JSONB` | Nullable |
| `after_value` | `JSONB` | Nullable |
| `ip_address` | `INET` | Nullable |
| `user_agent` | `TEXT` | Nullable |
| `request_id` | `VARCHAR(80)` | Nullable |
| `created_at` | `TIMESTAMPTZ` | Not null |

Indexes: `actor_user_id`, `(entity_type, entity_id)`, `action`, `created_at DESC`. Audit logs are append-only; no update/delete repository methods are exposed.

#### `notifications`

| Field | Type | Constraints |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `user_id` | `UUID` | FK -> `users.id` |
| `type` | `VARCHAR(60)` | Not null |
| `title` | `VARCHAR(200)` | Not null |
| `body` | `TEXT` | Not null |
| `metadata` | `JSONB` | Nullable |
| `read_at` | `TIMESTAMPTZ` | Nullable |

Indexes: `user_id`, `read_at`, `created_at DESC`.

#### `saved_events`

| Field | Type | Constraints |
| --- | --- | --- |
| `user_id` | `UUID` | FK -> `users.id` |
| `event_id` | `UUID` | FK -> `events.id` |
| `saved_at` | `TIMESTAMPTZ` | Not null |

Primary key: `(user_id, event_id)`.

## 7. Entity Relationship Explanation

One source can create many ingestion jobs through scheduled or manual triggers. One ingestion job can create many raw fetched items. Each raw fetched item can create one normalized item. One normalized item may become one event, or it may be ignored when it is duplicate, irrelevant, invalid, or below quality threshold.

One event can have many sources through `event_sources`, allowing source corroboration and reliability scoring. One event can have many timeline entries and locations. One user can have many watchlists, and each watchlist can include many country, category, keyword, actor, or event filters.

One intel cluster can contain many events through `cluster_events`. One event can have many AI suggestions, and AI suggestions remain auditable even when rejected. One event can have duplicate candidates against other events. Admin and analyst actions are written to immutable audit logs.

## 8. API Design

All routes are versioned under `/api/v1`. Responses use JSON. List endpoints support `page`, `page_size`, and relevant filters unless stated otherwise.

Common list response:

```json
{
  "items": [],
  "page": 1,
  "page_size": 25,
  "total": 0
}
```

### Authentication APIs

| Method | Endpoint | Description | Auth | Roles |
| --- | --- | --- | --- | --- |
| `POST` | `/auth/register` | Create user account | No | Public |
| `POST` | `/auth/login` | Authenticate and issue tokens | No | Public |
| `POST` | `/auth/refresh` | Rotate refresh token and issue access token | No | Public with refresh token |
| `POST` | `/auth/logout` | Revoke refresh token | Yes | All |
| `GET` | `/auth/me` | Return current user profile and roles | Yes | All |
| `POST` | `/auth/password-reset/request` | Request password reset | No | Public |
| `POST` | `/auth/password-reset/confirm` | Confirm password reset | No | Public |

`POST /auth/login`

Request:

```json
{
  "email": "analyst@example.com",
  "password": "StrongPassword123!"
}
```

Response:

```json
{
  "access_token": "jwt-access-token",
  "refresh_token": "opaque-refresh-token",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "email": "analyst@example.com",
    "roles": ["analyst"]
  }
}
```

### Users/Admin APIs

| Method | Endpoint | Description | Request Body | Response Body | Auth | Roles |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/users` | List users | Query filters | Paginated users | Yes | admin, superadmin |
| `GET` | `/users/{user_id}` | Get user detail | None | User detail | Yes | admin, superadmin |
| `PATCH` | `/users/{user_id}/roles` | Update user roles | `{"roles":["analyst"]}` | User detail | Yes | superadmin |
| `PATCH` | `/users/{user_id}/disable` | Disable user | `{"reason":"..."}` | User detail | Yes | admin, superadmin |
| `GET` | `/users/{user_id}/audit-logs` | Audit user actions | Query filters | Paginated audit logs | Yes | admin, superadmin |

### External Source APIs

| Method | Endpoint | Description | Request Body | Response Body | Auth | Roles |
| --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/sources` | Create source | ExternalSourceCreate | ExternalSourceResponse | Yes | admin, superadmin |
| `GET` | `/sources` | List sources | Query filters | Paginated sources | Yes | analyst, admin, superadmin |
| `GET` | `/sources/{source_id}` | Source detail | None | Source detail | Yes | analyst, admin, superadmin |
| `PATCH` | `/sources/{source_id}` | Update source | ExternalSourceUpdate | Source detail | Yes | admin, superadmin |
| `PATCH` | `/sources/{source_id}/disable` | Disable source | Reason | Source detail | Yes | admin, superadmin |
| `POST` | `/sources/{source_id}/test` | Test connector | None | Test result | Yes | admin, superadmin |
| `GET` | `/sources/{source_id}/reliability` | Reliability history | None | Reliability stats | Yes | analyst, admin, superadmin |

`POST /sources`

Request:

```json
{
  "name": "Example Conflict RSS",
  "connector_type": "rss",
  "base_url": "https://example.org/feed.xml",
  "auth_type": "none",
  "fetch_interval_minutes": 30,
  "rate_limit_per_hour": 60,
  "reliability_score": 0.72,
  "country_scope": null,
  "category_scope": ["war", "protest"]
}
```

Response:

```json
{
  "id": "uuid",
  "name": "Example Conflict RSS",
  "connector_type": "rss",
  "enabled": true,
  "created_at": "2026-06-16T10:00:00Z"
}
```

### Ingestion APIs

| Method | Endpoint | Description | Request Body | Response Body | Auth | Roles |
| --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/ingestion/sources/{source_id}/trigger` | Trigger source ingestion | `{"reason":"manual check"}` | Job response | Yes | analyst, admin, superadmin |
| `GET` | `/ingestion/jobs` | List jobs | Query filters | Paginated jobs | Yes | analyst, admin, superadmin |
| `GET` | `/ingestion/jobs/{job_id}` | Job detail | None | Job detail | Yes | analyst, admin, superadmin |
| `POST` | `/ingestion/jobs/{job_id}/retry` | Retry failed job | None | New job response | Yes | admin, superadmin |
| `GET` | `/ingestion/jobs/{job_id}/logs` | Job logs | Query filters | Paginated logs | Yes | analyst, admin, superadmin |
| `GET` | `/ingestion/raw-items` | Raw fetched items | Query filters | Paginated raw items | Yes | analyst, admin, superadmin |
| `GET` | `/ingestion/normalized-items` | Normalized items | Query filters | Paginated normalized items | Yes | analyst, admin, superadmin |

`POST /ingestion/sources/{source_id}/trigger`

Response:

```json
{
  "id": "uuid",
  "source_id": "uuid",
  "trigger_type": "manual",
  "status": "queued",
  "created_at": "2026-06-16T10:05:00Z"
}
```

### Review Queue APIs

| Method | Endpoint | Description | Request Body | Response Body | Auth | Roles |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/review-queue` | List pending review items | Query filters | Paginated queue items | Yes | analyst, admin, superadmin |
| `GET` | `/review-queue/{item_id}` | Review item detail | None | Review item detail | Yes | analyst, admin, superadmin |
| `POST` | `/review-queue/{item_id}/approve` | Approve pending event | Approval payload | Event response | Yes | analyst, admin, superadmin |
| `POST` | `/review-queue/{item_id}/reject` | Reject pending event | `{"reason":"..."}` | Queue item response | Yes | analyst, admin, superadmin |
| `POST` | `/review-queue/{item_id}/merge` | Merge duplicate event | Merge payload | Event response | Yes | analyst, admin, superadmin |
| `PATCH` | `/review-queue/{item_id}/event` | Edit event before approval | EventUpdate | Pending event response | Yes | analyst, admin, superadmin |

Approval request:

```json
{
  "verification_status": "verified",
  "risk_level": "high",
  "notes": "Confirmed by two reliable sources."
}
```

### Event APIs

| Method | Endpoint | Description | Request Body | Response Body | Auth | Roles |
| --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/events` | Create manual event | EventCreate | EventResponse | Yes | analyst, admin, superadmin |
| `GET` | `/events` | Get published events | Query filters | Paginated events | Optional | Public/user/analyst/admin |
| `GET` | `/events/{event_id}` | Get event detail | None | EventResponse | Optional | Public/user/analyst/admin |
| `PATCH` | `/events/{event_id}` | Update event | EventUpdate | EventResponse | Yes | analyst, admin, superadmin |
| `DELETE` | `/events/{event_id}` | Archive event | Archive reason | EventResponse | Yes | admin, superadmin |
| `POST` | `/events/{event_id}/verify` | Change verification status | Verification payload | EventResponse | Yes | analyst, admin, superadmin |
| `POST` | `/events/{event_id}/risk-level` | Change risk level | Risk payload | EventResponse | Yes | analyst, admin, superadmin |
| `POST` | `/events/{event_id}/sources` | Add source to event | Source link payload | EventSourceResponse | Yes | analyst, admin, superadmin |
| `POST` | `/events/{event_id}/timeline` | Add timeline update | Timeline payload | TimelineResponse | Yes | analyst, admin, superadmin |

Event filters: `country`, `category`, `risk_level`, `verification_status`, `date_from`, `date_to`, `keyword`, `source_id`, `published_only`.

`POST /events`

Request:

```json
{
  "title": "Border shelling reported near Example Valley",
  "summary": "Multiple sources report shelling near the border area.",
  "description": "Analyst-entered details and context.",
  "category_slug": "border_dispute",
  "risk_level": "medium",
  "verification_status": "developing",
  "event_date": "2026-06-16T08:30:00Z",
  "locations": [
    {
      "country_code": "EX",
      "country_name": "Exampleland",
      "admin_area": "North Province",
      "place_name": "Example Valley",
      "latitude": 12.345678,
      "longitude": 76.543210,
      "location_precision": "city",
      "confidence": 0.81
    }
  ],
  "tags": ["border", "shelling"]
}
```

Response:

```json
{
  "id": "uuid",
  "title": "Border shelling reported near Example Valley",
  "risk_level": "medium",
  "verification_status": "developing",
  "publication_status": "pending_review",
  "created_at": "2026-06-16T10:10:00Z"
}
```

### Map APIs

| Method | Endpoint | Description | Request Body | Response Body | Auth | Roles |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/map/events` | Get map-ready events | Query filters | Map markers | Optional | Public/user/analyst/admin |
| `GET` | `/map/events/bbox` | Events inside bounding box | Query params | Map markers | Optional | Public/user/analyst/admin |
| `GET` | `/map/countries/counts` | Country-wise event count | Query filters | Country counts | Optional | Public/user/analyst/admin |
| `GET` | `/map/high-risk-markers` | High-risk markers | Query filters | Marker list | Optional | Public/user/analyst/admin |

Bounding-box query: `?min_lat=10&min_lng=70&max_lat=20&max_lng=80&risk_level=high`.

### Dashboard APIs

| Method | Endpoint | Description | Auth | Roles |
| --- | --- | --- | --- | --- |
| `GET` | `/dashboard/summary` | Total events and headline metrics | Yes | user, analyst, admin, superadmin |
| `GET` | `/dashboard/events-by-risk` | Events grouped by risk | Yes | user, analyst, admin, superadmin |
| `GET` | `/dashboard/events-by-category` | Events grouped by category | Yes | user, analyst, admin, superadmin |
| `GET` | `/dashboard/events-by-country` | Events grouped by country | Yes | user, analyst, admin, superadmin |
| `GET` | `/dashboard/verification-stats` | Verified vs unverified counts | Yes | analyst, admin, superadmin |
| `GET` | `/dashboard/recent-high-risk` | Recent high-risk alerts | Yes | user, analyst, admin, superadmin |
| `GET` | `/dashboard/ingestion-stats` | Ingestion success/failure stats | Yes | analyst, admin, superadmin |

### Watchlist APIs

| Method | Endpoint | Description | Request Body | Response Body | Auth | Roles |
| --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/watchlists` | Create watchlist | WatchlistCreate | WatchlistResponse | Yes | user, analyst, admin, superadmin |
| `GET` | `/watchlists` | List own watchlists | None | Watchlists | Yes | user, analyst, admin, superadmin |
| `POST` | `/watchlists/{watchlist_id}/items` | Add watchlist item | WatchlistItemCreate | ItemResponse | Yes | user, analyst, admin, superadmin |
| `GET` | `/watchlists/{watchlist_id}/feed` | Watchlist event feed | Query filters | Paginated events | Yes | user, analyst, admin, superadmin |
| `DELETE` | `/watchlists/{watchlist_id}/items/{item_id}` | Delete item | None | Empty success | Yes | user, analyst, admin, superadmin |

### Intel Cluster APIs

| Method | Endpoint | Description | Request Body | Response Body | Auth | Roles |
| --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/clusters` | Create cluster | ClusterCreate | ClusterResponse | Yes | analyst, admin, superadmin |
| `GET` | `/clusters` | List clusters | Query filters | Paginated clusters | Yes | analyst, admin, superadmin |
| `GET` | `/clusters/{cluster_id}` | Cluster details | None | ClusterResponse | Yes | analyst, admin, superadmin |
| `POST` | `/clusters/{cluster_id}/events` | Add event to cluster | `{"event_id":"uuid"}` | ClusterResponse | Yes | analyst, admin, superadmin |
| `DELETE` | `/clusters/{cluster_id}/events/{event_id}` | Remove event | None | ClusterResponse | Yes | analyst, admin, superadmin |

### AI APIs

AI APIs create suggestions, not final state changes.

| Method | Endpoint | Description | Request Body | Response Body | Auth | Roles |
| --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/ai/summary` | Generate summary suggestion | Text/event ref | AISuggestionResponse | Yes | analyst, admin, superadmin |
| `POST` | `/ai/category` | Suggest category | Text/event ref | AISuggestionResponse | Yes | analyst, admin, superadmin |
| `POST` | `/ai/risk-level` | Suggest risk level | Event data | AISuggestionResponse | Yes | analyst, admin, superadmin |
| `POST` | `/ai/verification-status` | Suggest verification | Event/source data | AISuggestionResponse | Yes | analyst, admin, superadmin |
| `POST` | `/ai/extract-event` | Extract event data from raw text | Raw text/ref | AISuggestionResponse | Yes | analyst, admin, superadmin |
| `POST` | `/ai/detect-duplicate` | Detect duplicate event | Event data | AISuggestionResponse | Yes | analyst, admin, superadmin |
| `POST` | `/ai/extract-location` | Extract location | Text/event ref | AISuggestionResponse | Yes | analyst, admin, superadmin |
| `POST` | `/ai/timeline` | Generate timeline suggestion | Text/event ref | AISuggestionResponse | Yes | analyst, admin, superadmin |

AI response:

```json
{
  "id": "uuid",
  "suggestion_type": "risk",
  "suggested_value": {
    "risk_level": "high",
    "score": 82,
    "reasons": ["civilian harm", "multiple sources", "geographic sensitivity"]
  },
  "confidence": 0.78,
  "status": "pending"
}
```

## 9. Authentication and Authorization

Authentication design:

| Control | Design |
| --- | --- |
| Access token | JWT signed with strong secret or asymmetric key, short lifetime, contains subject, roles, permissions, and token id. |
| Refresh token | Opaque random token, stored hashed, rotated on each refresh, expires after configured period. |
| Password hashing | Argon2id preferred; bcrypt acceptable if Argon2id is unavailable. |
| RBAC | Route dependencies require permission codes; roles map to permission sets. |
| Account state | Disabled users cannot refresh tokens or call protected APIs. |
| Session revocation | Logout clears refresh token hash; password change revokes sessions. |

Permission matrix:

| Capability | guest | user | analyst | admin | superadmin |
| --- | --- | --- | --- | --- | --- |
| View public published events | Yes | Yes | Yes | Yes | Yes |
| Create watchlists | No | Yes | Yes | Yes | Yes |
| Save events | No | Yes | Yes | Yes | Yes |
| View dashboard user metrics | No | Yes | Yes | Yes | Yes |
| View ingestion data | No | No | Yes | Yes | Yes |
| Trigger manual ingestion | No | No | Yes | Yes | Yes |
| Review pending events | No | No | Yes | Yes | Yes |
| Edit events | No | No | Yes | Yes | Yes |
| Verify events | No | No | Yes | Yes | Yes |
| Manage sources | No | No | No | Yes | Yes |
| Manage users | No | No | No | Yes | Yes |
| Assign roles | No | No | No | No | Yes |
| View audit logs | No | No | No | Yes | Yes |
| System settings | No | No | No | No | Yes |

## 10. Event Lifecycle

```text
Fetched Raw Item
  -> Normalized Item
  -> AI Suggested Event
  -> Pending Review
  -> Developing / Verified / Disputed / False
  -> Published
  -> Updated
  -> Archived
```

Lifecycle controls:

| Transition | Allowed Roles | Notes |
| --- | --- | --- |
| Raw item -> normalized item | System | Automatic pipeline. |
| Normalized item -> pending event | System | Created as `pending_review`; not public. |
| Pending event -> developing | analyst, admin, superadmin | Usually when credible but not fully confirmed. |
| Pending event -> verified | analyst, admin, superadmin | Requires source and confidence checks. |
| Pending event -> disputed | analyst, admin, superadmin | Used when credible reports conflict. |
| Pending event -> false | analyst, admin, superadmin | Stored for audit and duplicate suppression. |
| Pending event -> published | analyst, admin, superadmin | Requires review action. |
| Published -> updated | analyst, admin, superadmin | Creates audit log and may notify watchers. |
| Published -> archived | admin, superadmin | Soft archive with reason. |

## 11. Risk Scoring Design

Risk levels:

| Score | Level |
| --- | --- |
| `0-39` | Low |
| `40-69` | Medium |
| `70-100` | High |

Rule factors:

| Factor | Example Scoring |
| --- | --- |
| Casualties | `0-20` based on confirmed or reported casualty count. |
| Military involvement | `0-15` when state military, armed groups, or border forces are involved. |
| Cyber infrastructure impact | `0-15` for critical systems, national infrastructure, finance, health, or telecom. |
| Number of sources | `0-10` based on independent corroboration. |
| Official confirmation | `0-10` from government, emergency agency, court, or official military source. |
| Civilian harm | `0-15` for deaths, displacement, hostages, or blocked aid. |
| Geographic sensitivity | `0-10` for border zones, disputed territories, capitals, chokepoints, or sensitive infrastructure. |
| Escalation possibility | `0-10` based on actors, prior incidents, proximity, and rhetoric. |
| Source reliability | `-10` to `+10` based on reliability snapshot. |
| Social-media-only reports | `-15` penalty until corroborated. |
| Repetition in same region | `0-10` for recurring events in recent time window. |
| AI extraction confidence | `-10` to `+5`; low confidence reduces score, high confidence modestly supports it. |

Risk score is recalculated whenever sources, verification status, casualties, category, or location change. Manual overrides require reason and audit log.

## 12. Verification Workflow

Statuses:

| Status | Meaning |
| --- | --- |
| `unverified` | Insufficient corroboration or only one low-confidence source. |
| `developing` | Credible but still changing; details may be incomplete. |
| `verified` | Confirmed by reliable source(s) or strong independent corroboration. |
| `disputed` | Conflicting credible claims or contested facts. |
| `false` | Determined to be incorrect; retained for traceability and future duplicate suppression. |

Verification logic:

| Concern | Design |
| --- | --- |
| Fetched events | Enter review as pending with suggested verification status. |
| Source reliability | Higher reliability increases confidence but never bypasses review. |
| Multiple sources | Independent source corroboration improves verification score. |
| Admin/analyst approval | Required before status becomes public-facing verified or published. |
| Disputed information | Preserve competing claims in timeline or notes; mark status `disputed`. |
| False reports | Keep stored and archived from public feed unless admin views are requested. |
| Verification history | Store each status change in audit logs with before/after values, actor, reason, and timestamp. |

## 13. AI Integration Design

AI is an assistant layer. It suggests structured outputs that humans approve, reject, or edit.

AI can suggest:

| Suggestion | Output |
| --- | --- |
| Summary | Short event summary and longer analytical summary. |
| Category | Category slug with confidence and rationale. |
| Risk level | Risk level, score, and factor breakdown. |
| Verification status | Suggested status and corroboration reasoning. |
| Duplicate possibility | Candidate event ids and similarity reasons. |
| Timeline extraction | Ordered timeline entries. |
| Location extraction | Country, place, lat/lon if available, precision, confidence. |
| Actor/entity extraction | Organizations, people, state actors, infrastructure, affected groups. |
| Confidence score | Confidence per extracted field and overall extraction confidence. |

AI request flow:

```text
Service receives raw/normalized/event input
  -> Validate user role and input size
  -> Redact secrets and internal metadata
  -> Build prompt using versioned template
  -> Call AI provider with timeout and retry policy
  -> Validate response against schema
  -> Store suggestion in ai_suggestions
  -> Return suggestion id to analyst/admin
```

AI response format:

```json
{
  "summary": "Short factual summary.",
  "category": {
    "slug": "protest",
    "confidence": 0.83
  },
  "risk": {
    "level": "medium",
    "score": 61,
    "factors": [
      {"name": "civilian_harm", "points": 10},
      {"name": "source_reliability", "points": 6}
    ]
  },
  "locations": [
    {
      "country_name": "Exampleland",
      "place_name": "Capital City",
      "latitude": 12.345678,
      "longitude": 76.543210,
      "precision": "city",
      "confidence": 0.74
    }
  ],
  "confidence": 0.79
}
```

Safety rules:

| Rule | Enforcement |
| --- | --- |
| No auto-publication | AI service has no event publication method. |
| Structured output only | Responses validated against Pydantic schemas. |
| Prompt versioning | Every suggestion records prompt version and model name. |
| Secret protection | Source credentials and tokens are never sent to AI. |
| Low confidence handling | Low-confidence suggestions remain pending and flagged. |
| Rate limits | Redis counters and provider-specific backoff. |
| Failure handling | Store failure in ingestion logs; continue non-AI pipeline where possible. |
| Auditability | Store suggestion, input hash, confidence, reviewer decision, and timestamps. |

## 14. Services and Business Logic

| Service | Responsibility | Major Methods | Input | Output | Dependencies |
| --- | --- | --- | --- | --- | --- |
| `AuthService` | Registration, login, refresh, logout | `register`, `login`, `refresh`, `logout` | Credentials, token | Token/user response | UserRepository, password, JWT |
| `UserService` | User and role management | `list_users`, `assign_roles`, `disable_user` | User ids, role names | User DTO | UserRepository, AuditLogService |
| `SourceService` | Source CRUD and testing | `create_source`, `update_source`, `test_source` | Source DTO | Source DTO/test result | SourceRepository, ConnectorService |
| `IngestionService` | End-to-end ingestion jobs | `trigger`, `run_job`, `retry_job` | Source/job id | Job result | ConnectorService, repositories, pipeline services |
| `ConnectorService` | Resolve and execute connector | `get_connector`, `fetch` | Source config | Raw connector records | Connector classes |
| `NormalizationService` | Normalize raw items | `normalize_raw_item` | Raw item | Normalized item | Normalizers |
| `EventExtractionService` | Extract event candidate | `extract_event_candidate` | Normalized item | Event draft | AIService, rules |
| `DeduplicationService` | Find duplicate candidates | `find_candidates`, `record_candidate` | Event draft | Candidate list | EventRepository, similarity |
| `EventService` | Event CRUD and publication | `create_manual`, `update`, `publish`, `archive` | Event DTOs | Event DTO | EventRepository, AuditLogService |
| `SourceLinkingService` | Link evidence to events | `add_source`, `list_sources` | Event/source ids | EventSource DTO | EventSourceRepository |
| `RiskScoringService` | Score events | `score_event`, `explain_score` | Event draft/event | Risk result | Source data, AI suggestions |
| `VerificationService` | Verification rules | `suggest_status`, `change_status` | Event/source data | Status result | EventRepository, AuditLogService |
| `ReviewQueueService` | Review workflow | `enqueue`, `approve`, `reject`, `merge` | Queue item/action | Queue/event DTO | ReviewQueueRepository, EventService |
| `WatchlistService` | Watchlists and matching | `create`, `add_item`, `feed` | User/filter data | Watchlist/feed | WatchlistRepository, EventRepository |
| `ClusterService` | Intel clusters | `create`, `add_event`, `remove_event` | Cluster/event ids | Cluster DTO | ClusterRepository |
| `DashboardService` | Aggregations | `summary`, `by_risk`, `ingestion_stats` | Filters | Stats DTO | EventRepository, cache |
| `MapService` | Geospatial queries | `markers`, `bbox`, `country_counts` | Map filters | Map DTO | EventRepository, cache |
| `AIService` | AI suggestions | `summarize`, `extract`, `suggest_risk` | Text/event data | AI suggestion | AI client, AISuggestionRepository |
| `NotificationService` | Notify users | `notify_watchlist_match`, `notify_ingestion_failure` | Event/user data | Notification DTO | NotificationRepository |
| `AuditLogService` | Immutable audit | `record` | Actor/action/before/after | Audit log id | AuditLogRepository |

## 15. Repository Layer Design

Repositories isolate persistence and query optimization.

| Repository | Operations |
| --- | --- |
| `UserRepository` | Create users, get by email/id, list with filters, update status, update refresh token hash, manage roles. |
| `SourceRepository` | CRUD sources, list enabled sources, update reliability, update last success/failure. |
| `IngestionJobRepository` | Create job, transition status, update counters, list jobs, get failed jobs. |
| `RawFetchedItemRepository` | Insert raw items, detect raw duplicates, fetch by hash/source, update processing status. |
| `NormalizedItemRepository` | Insert normalized item, get by raw item, list by status, mark ignored/failed. |
| `EventRepository` | Create event, filter events, get detail with relationships, update risk/status, archive, full-text search, map queries. |
| `EventSourceRepository` | Link sources to events, list event sources, count independent sources, store reliability snapshots. |
| `WatchlistRepository` | Create watchlist, add/delete items, list user watchlists, resolve watchlist feed filters. |
| `ClusterRepository` | Create/update cluster, add/remove events, list cluster events. |
| `ReviewQueueRepository` | Enqueue items, lock item for review, transition status, assign reviewer, list pending queue. |
| `AuditLogRepository` | Append audit record and query audit history. No update/delete methods. |

## 16. Schemas / DTO Design

Important Pydantic schemas:

```python
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    password: SecretStr

class UserLogin(BaseModel):
    email: EmailStr
    password: SecretStr

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict

class ExternalSourceCreate(BaseModel):
    name: str
    connector_type: Literal["rss", "news_api", "dataset", "government_alert", "manual"]
    base_url: AnyUrl | None = None
    auth_type: Literal["none", "api_key", "bearer", "basic", "signed_url"] = "none"
    secret_ref: str | None = None
    fetch_interval_minutes: int
    rate_limit_per_hour: int | None = None
    reliability_score: Decimal
    country_scope: str | None = None
    category_scope: list[str] | None = None

class IngestionJobResponse(BaseModel):
    id: UUID
    source_id: UUID
    trigger_type: str
    status: str
    fetched_count: int
    duplicate_raw_count: int
    normalized_count: int
    pending_event_count: int
    started_at: datetime | None
    finished_at: datetime | None

class RawFetchedItemResponse(BaseModel):
    id: UUID
    source_id: UUID
    job_id: UUID
    source_url: str | None
    title: str | None
    content_hash: str
    published_at: datetime | None
    fetched_at: datetime
    processing_status: str

class NormalizedItemResponse(BaseModel):
    id: UUID
    raw_item_id: UUID
    normalized_title: str
    normalized_body: str
    language: str | None
    country_hint: str | None
    category_hint: str | None
    status: str

class EventCreate(BaseModel):
    title: str
    summary: str
    description: str | None = None
    category_slug: str
    risk_level: Literal["low", "medium", "high"]
    verification_status: Literal["unverified", "developing", "verified", "disputed", "false"]
    event_date: datetime
    locations: list[dict]
    tags: list[str] = []

class EventUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    description: str | None = None
    category_slug: str | None = None
    risk_level: Literal["low", "medium", "high"] | None = None
    verification_status: str | None = None
    event_date: datetime | None = None
    locations: list[dict] | None = None
    tags: list[str] | None = None
    change_reason: str

class EventResponse(BaseModel):
    id: UUID
    title: str
    summary: str
    category: dict
    risk_level: str
    risk_score: Decimal
    verification_status: str
    publication_status: str
    event_date: datetime
    locations: list[dict]
    sources: list[dict]
    tags: list[str]

class ReviewQueueItemResponse(BaseModel):
    id: UUID
    event_id: UUID
    queue_type: str
    priority: int
    status: str
    assigned_to: UUID | None
    created_reason: str | None

class WatchlistCreate(BaseModel):
    name: str
    description: str | None = None

class ClusterCreate(BaseModel):
    name: str
    description: str | None = None
    risk_level: Literal["low", "medium", "high"] | None = None

class AISuggestionResponse(BaseModel):
    id: UUID
    suggestion_type: str
    suggested_value: dict
    confidence: Decimal | None
    status: str
    model_name: str
    prompt_version: str

class DashboardStatsResponse(BaseModel):
    total_events: int
    high_risk_events: int
    verified_events: int
    pending_review_count: int
    ingestion_success_rate: Decimal

class MapEventResponse(BaseModel):
    event_id: UUID
    title: str
    category: str
    risk_level: str
    verification_status: str
    latitude: Decimal | None
    longitude: Decimal | None
    country_code: str | None
    country_name: str
    event_date: datetime
```

## 17. Error Handling

Standard error format:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Event not found.",
    "details": {
      "event_id": "uuid"
    },
    "request_id": "req_123",
    "timestamp": "2026-06-16T10:15:00Z"
  }
}
```

Status mapping:

| Status | Use |
| --- | --- |
| `400 Bad Request` | Invalid business input or unsupported operation. |
| `401 Unauthorized` | Missing, expired, or invalid token. |
| `403 Forbidden` | Authenticated user lacks permission. |
| `404 Not Found` | Entity does not exist or is not visible to role. |
| `409 Conflict` | Duplicate source, duplicate raw item, merge conflict, stale update. |
| `422 Validation Error` | Pydantic validation failure. |
| `429 Rate Limit Exceeded` | API, auth, AI, or source-trigger rate exceeded. |
| `500 Internal Server Error` | Unexpected application failure. |
| `502 External Source Failure` | Connector received invalid or failed external response. |
| `503 Ingestion Service Unavailable` | Scheduler/job system unavailable or locked. |

## 18. Logging and Audit Trail

Structured application logs include `request_id`, `actor_user_id`, route, status code, duration, source id, job id, event id, and error details when applicable.

Audit events:

| Event | Storage |
| --- | --- |
| User login | Security log and audit log for admin-visible history. |
| Source creation/update | Audit before/after values. |
| Ingestion job started | Ingestion log. |
| Ingestion job failed | Ingestion log with retry metadata. |
| Raw item fetched | Ingestion counters and optional debug log. |
| Event extracted | Ingestion log and event creation audit. |
| Duplicate detected | Duplicate candidate row plus ingestion log. |
| Event creation | Audit log. |
| Event update | Audit before/after values. |
| Risk level change | Audit with reason and scorer details. |
| Verification change | Audit with reason and actor. |
| Source update | Audit before/after values. |
| Admin review action | Review queue decision and audit log. |
| AI suggestion generated | AI suggestion row and ingestion/API log. |

Audit logs are immutable. The application exposes append-only writes and read-only queries.

## 19. Security Design

| Area | Design |
| --- | --- |
| Password hashing | Argon2id with per-password salt and strong parameters. |
| JWT security | Short-lived access token, signed securely, includes token id, role claims, and issued-at timestamp. |
| Refresh tokens | Opaque, random, hashed at rest, rotated on refresh, revoked on logout/password change. |
| Rate limiting | Redis counters for auth, AI, source testing, manual ingestion, and high-cost endpoints. |
| CORS | Explicit allowed origins per environment; credentials only for trusted frontend domains. |
| Input validation | Pydantic schemas, enum constraints, strict length limits, URL validation. |
| SQL injection prevention | SQLAlchemy parameter binding; no string-concatenated SQL. |
| XSS prevention at API level | Store plain text or sanitized rich text; frontend escapes output; API rejects unsafe HTML fields unless explicitly allowed. |
| External URL validation | Allow only HTTP/HTTPS, block localhost/private networks for external fetchers, enforce DNS/IP checks. |
| SSRF protection | Deny private IP ranges, link-local addresses, metadata endpoints, redirects to blocked ranges, and unsupported schemes. |
| API keys | Stored outside code in environment or secret manager references. |
| Environment variables | Required at startup with strict validation. |
| Admin route protection | Permission dependency and audit logging. |
| Ingestion abuse prevention | Manual triggers rate-limited, role-gated, source-locked, and logged. |

## 20. Performance and Scalability

| Topic | Design |
| --- | --- |
| Indexing | Index high-cardinality filters: dates, risk, category, status, country, source, job, and full-text fields. |
| Pagination | Cursor pagination for live feed; page pagination for admin tables. |
| Caching | Cache dashboard aggregates, map marker clusters, source reliability stats, and common feed filters. |
| Query optimization | Use eager loading for event detail, projection queries for map markers, and aggregate materialization for dashboards. |
| Background jobs | Keep ingestion outside request latency; manual trigger returns job id. |
| Async processing | Use async HTTP clients for connectors and FastAPI request handling. |
| Map marker optimization | Return compact marker DTOs, bounding-box filters, clustering support, and risk/category filters. |
| Dashboard optimization | Precompute hourly/daily aggregates for high-traffic dashboards. |
| Source fetch control | Rate-limit per source, honor provider limits, and stagger schedules. |
| Batch inserts | Insert raw and normalized records in batches where connector responses are large. |
| Retry queues | Retry transient connector and AI failures with backoff. |
| Duplicate processing | Use hashes before expensive similarity checks; lock candidate processing per source/job. |

## 21. Deployment Design For Servers, VMs, And PaaS

Production deployment targets a VM, cloud instance, or PaaS runtime using Python virtual environments and managed services where possible.

Deployment components:

| Component | Design |
| --- | --- |
| Python environment | Create a virtual environment, install locked dependencies, run application as a non-root service user. |
| API process | Run Gunicorn with Uvicorn workers for FastAPI. |
| Reverse proxy | Nginx terminates HTTPS, forwards API traffic, sets proxy headers, and enforces body size limits. |
| Process manager | systemd service for API and separate service for scheduler/worker process. |
| Environment management | Store production variables in restricted env files or platform secret settings. |
| Database migrations | Run Alembic migrations during release before service restart. |
| PostgreSQL | Managed PostgreSQL preferred; self-hosted PostgreSQL acceptable with backups and monitoring. |
| Redis | Managed Redis or secured server Redis for cache, locks, and rate limits. |
| SSL/HTTPS | Use platform certificates or Certbot-managed certificates with renewal checks. |
| Domain | Point API subdomain to reverse proxy and configure allowed CORS origins. |
| CI/CD | Pull from GitHub, install dependencies, run tests, run migrations, restart services, verify health. |
| Health check | `/health` verifies API process, database connectivity, Redis connectivity, and scheduler heartbeat. |
| Log rotation | Rotate application, access, error, and scheduler logs. |
| Backups | Daily database backups, point-in-time recovery where supported, restore drills. |
| Rollback | Keep previous release directory and dependency lock; rollback code then run compatible migration plan. |
| Monitoring | Track latency, error rate, job failures, queue age, database health, and disk usage. |

Example systemd unit shape:

```ini
[Unit]
Description=GeoAtlas FastAPI service
After=network.target

[Service]
User=geoatlas
Group=geoatlas
WorkingDirectory=/opt/geo-atlas/current
EnvironmentFile=/etc/geo-atlas/production.env
ExecStart=/opt/geo-atlas/venv/bin/gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 4 --bind 127.0.0.1:8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 22. Scheduler and Background Jobs

Scheduler choice: APScheduler for the first production deployment because source schedules are interval-based, operationally simple, and can run as a dedicated service process. If ingestion volume grows substantially, move job execution to Celery or RQ while keeping the same service and repository boundaries.

Scheduler design:

| Concern | Design |
| --- | --- |
| Job registration | On scheduler startup, load enabled sources and register interval jobs using `fetch_interval_minutes`. |
| Manual fetch | API creates manual job and runner executes immediately if source lock is free. |
| Retry | Retry transient failures with exponential backoff; failed final state remains queryable. |
| Logging | Every job writes `ingestion_jobs` and detailed `ingestion_logs`. |
| Status tracking | Status transitions: `queued -> running -> success/partial_failure/failed/cancelled`. |
| Concurrent conflicts | Redis lock key `ingestion:source:{source_id}` prevents overlapping jobs for the same source. |
| Long-running jobs | Enforce job timeout, heartbeat updates, and cancellation markers. |
| Stale locks | Locks have TTL and heartbeat validation. |
| Admin visibility | Ingestion dashboard exposes active jobs, failure rate, queue age, and last success per source. |

## 23. Testing Strategy

| Test Type | Coverage |
| --- | --- |
| Unit tests | Services, scoring rules, verification rules, URL safety, hashing, normalization helpers. |
| Integration tests | PostgreSQL repositories, transactions, Alembic migrations, Redis locks, cache invalidation. |
| API tests | Route validation, pagination, filters, error formats, response schemas. |
| Authentication tests | Register, login, refresh rotation, logout, disabled users, expired tokens. |
| Role permission tests | Ensure user, analyst, admin, and superadmin boundaries are enforced. |
| Database tests | Constraints, indexes, relationships, duplicate raw item prevention. |
| Ingestion pipeline tests | Source job to pending review flow with mocked connector data. |
| Source connector mock tests | RSS, news API, dataset, government alert, manual payloads. |
| AI service mock tests | Schema validation, timeout handling, rate limit handling, failed responses. |
| Deduplication tests | Hash match, title similarity, location/time proximity, false-positive rejection. |
| Review workflow tests | Approve, reject, edit-before-approval, merge duplicate, audit log generation. |

## 24. Sample Backend Flows

### Auto Fetched Event

```text
Scheduler triggers source fetch
  -> Connector fetches raw data
  -> Raw item saved
  -> Normalizer cleans data
  -> AI extracts event details
  -> Duplicate check runs
  -> Risk score is suggested
  -> Pending review item is created
  -> Analyst approves
  -> Published event appears in feed/map/dashboard
```

### User Views Live Feed

```text
Request
  -> Optional auth dependency resolves user context
  -> Filters and pagination validated
  -> EventRepository runs optimized published-event query
  -> Service adds saved/watchlist flags when authenticated
  -> Response returned
```

### Admin Reviews Event

```text
Request
  -> Auth middleware validates token
  -> Role check confirms analyst/admin permission
  -> Pending review item loaded and locked
  -> Admin edits or approves event
  -> Event publication status changes
  -> Audit log saved
  -> Watchlist notifications are queued
```

### AI Summary Generation

```text
Fetched or manual text
  -> Backend validates analyst/admin permission
  -> Backend sends sanitized text to AI service
  -> AI returns structured suggestion
  -> Suggestion saved
  -> Admin/analyst approves manually if useful
```

## 25. Final Deliverables

### Final Backend Module List

```text
auth
users
sources
ingestion
connectors
normalization
event_extraction
deduplication
risk_scoring
verification
review_queue
events
map
dashboard
watchlists
intel_clusters
ai
notifications
audit_logs
logging
monitoring
deployment
```

### Final Table List

```text
users
roles
permissions
role_permissions
user_roles
external_sources
ingestion_jobs
ingestion_logs
raw_fetched_items
normalized_items
events
event_sources
event_categories
event_tags
event_timelines
event_locations
watchlists
watchlist_items
intel_clusters
cluster_events
ai_suggestions
duplicate_candidates
review_queue
audit_logs
notifications
saved_events
```

### Final API Route List

```text
/api/v1/auth/*
/api/v1/users/*
/api/v1/sources/*
/api/v1/ingestion/*
/api/v1/review-queue/*
/api/v1/events/*
/api/v1/map/*
/api/v1/dashboard/*
/api/v1/watchlists/*
/api/v1/clusters/*
/api/v1/ai/*
/api/v1/notifications/*
/api/v1/public/*
/health
/openapi.json
```

### Final Ingestion Pipeline List

```text
fetch_raw_data
store_raw_item
normalize_item
extract_event_candidate
extract_location
extract_category
generate_ai_suggestions
detect_duplicates
score_risk
suggest_verification
create_pending_event
enqueue_review
publish_after_human_review
```

### Final Service List

```text
AuthService
UserService
SourceService
IngestionService
ConnectorService
NormalizationService
EventExtractionService
DeduplicationService
EventService
SourceLinkingService
RiskScoringService
VerificationService
ReviewQueueService
WatchlistService
ClusterService
DashboardService
MapService
AIService
NotificationService
AuditLogService
```

### Development Priority Order

1. Project foundation: FastAPI app, config, DB session, migrations, errors, logging.
2. Auth and RBAC: users, roles, JWT, refresh tokens, permission dependencies.
3. Core event model: categories, events, locations, sources, timelines, tags.
4. Source management: source CRUD, validation, connector test endpoint.
5. Ingestion foundation: jobs, logs, raw items, scheduler, locks.
6. Connectors and normalizers: RSS first, then news API, datasets, government alerts, manual input.
7. Event extraction and review queue: pending events, edit/approve/reject.
8. Deduplication and risk scoring: candidate detection, scoring explanations, merge flow.
9. Verification workflow: status changes, history, disputed/false handling.
10. Feed, map, dashboard APIs: optimized read paths, pagination, filters, cache.
11. Watchlists and notifications: matching logic and user alerts.
12. Intel clusters: related-event grouping and analyst workflows.
13. AI suggestions: structured suggestions, auditability, approval handling.
14. Production hardening: rate limits, SSRF protections, monitoring, backups, deployment scripts.
15. Test expansion and load testing: ingestion, map queries, dashboards, RBAC, failure paths.

### Final Deployment Checklist

```text
Create production PostgreSQL database
Create production Redis instance
Create service user on server
Create Python virtual environment
Install pinned dependencies
Configure production environment variables
Run Alembic migrations
Create initial superadmin
Configure Gunicorn/Uvicorn API service
Configure scheduler service
Configure Nginx reverse proxy
Configure HTTPS certificate
Configure CORS allowed origins
Configure log rotation
Configure database backups
Configure monitoring and alerts
Run smoke tests
Verify /health endpoint
Verify login, source test, manual ingestion, review approval, feed, map, dashboard
Document rollback procedure
```
