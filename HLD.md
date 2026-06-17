# GeoAtlas Backend High Level Design

Project work history is maintained in [documentation.md](documentation.md). The runnable data-collection backend is in [backend/](backend/) and implementation notes are in [docs/GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md](docs/GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md).

## 1. Purpose

GeoAtlas is a production-ready Geo-Intelligence and Conflict Monitoring Platform. It tracks geopolitical, crisis, security, humanitarian, cyber, natural disaster, and instability events from automated external sources and analyst/admin workflows.

This High Level Design defines the backend architecture, major subsystems, integration boundaries, data flows, deployment model, security posture, and operational strategy. The detailed implementation-level schema, services, repositories, and API route definitions are covered in the Low Level Design.

## 2. Design Goals

| Goal | Description |
| --- | --- |
| Automated intelligence ingestion | Continuously fetch event data from RSS, news APIs, public datasets, government alerts, NGO reports, and OSINT-style public sources. |
| Human-controlled publishing | AI and automated systems can suggest events, but only analysts/admins can approve publication. |
| Geospatial event discovery | Support live feed, map view, dashboard analytics, country filters, bounding-box queries, and high-risk markers. |
| Strong moderation workflow | Provide review queues, duplicate resolution, verification changes, risk updates, and immutable audit logs. |
| Production deployability | Run on a normal server, cloud VM, or PaaS using virtual environment, process manager, reverse proxy, PostgreSQL, and Redis. |
| Traceability | Preserve raw fetched data, normalized data, AI suggestions, source links, review decisions, and audit history. |
| Scalable read APIs | Keep feed, map, dashboard, and watchlist APIs fast through indexes, pagination, caching, and precomputed aggregates. |

## 3. Scope

In scope:

| Area | Included |
| --- | --- |
| Backend APIs | Authentication, users, sources, ingestion, review queue, events, map, dashboard, watchlists, clusters, AI suggestions, notifications. |
| Data ingestion | Scheduled and manual fetching, connector execution, raw storage, normalization, event extraction, deduplication, risk scoring. |
| Human review | Analyst/admin event approval, rejection, edit-before-approval, merge duplicate, verification updates. |
| AI assistance | Summaries, categories, locations, risk suggestions, verification suggestions, duplicate candidates, timelines, entity extraction. |
| Persistence | Supabase PostgreSQL with PostGIS for relational storage, raw payload retention, geospatial event locations, full-text search, and public API read models. |
| Caching and coordination | Redis for cache, rate limits, ingestion locks, and background coordination. |
| Operations | Health checks, logs, monitoring, backup, rollback, migration, and service process design. |
| Source administration UI | A small internal frontend for adding RSS/feed links, testing feed detection, viewing ingestion status, and previewing extracted output. |

Out of scope:

| Area | Exclusion |
| --- | --- |
| Public news frontend | The system exposes public output APIs, but does not require a frontend that displays news items or events. |
| Mobile app implementation | Mobile clients may consume APIs but are not designed here. |
| Direct AI publishing | AI cannot independently publish, verify, or archive events. |
| Alternate packaging models | Deployment uses VM/server/PaaS process management and reverse proxy setup. |

## 4. System Context

```text
External Data Sources
  |-- RSS feeds
  |-- Atom feeds
  |-- News APIs
  |-- Public datasets
  |-- Government alerts
  |-- NGO reports
  |-- Manual analyst input
        |
        v
GeoAtlas Backend
  |-- GeoAtlas source collection API
  |-- Ingestion and normalization
  |-- AI-assisted extraction
  |-- Deduplication and risk scoring
  |-- Human review workflow
  |-- Public output APIs
        |
        +--------------------+--------------------+--------------------+--------------------+
        |                    |                    |                    |                    |
        v                    v                    v                    v                    v
GeoAtlas Feed UI         Public API Clients   Analyst Console       Admin Console       Internal Ops
  |-- Add feed URL      |-- JSON output     |-- Review queue       |-- Sources          |-- Health checks
  |-- Test detection    |-- Export output   |-- Event edits        |-- Users            |-- Logs
  |-- Trigger ingest    |-- Poll jobs       |-- Duplicates         |-- Audit logs       |-- Scheduler status
  |-- Preview output    |-- Map data        |-- Verification       |-- System controls  |-- Backups
```

## 5. High Level Architecture

```text
                                      +----------------------+
                                      | External AI Provider |
                                      +----------+-----------+
                                                 ^
                                                 |
+-------------------+      +---------------------+---------------------+
| External Sources  | ---> | GeoAtlas Ingestion and Processing Layer    |
+-------------------+      | - Source connectors                       |
                           | - Raw item storage                        |
                           | - Normalization                           |
                           | - Event extraction                        |
                           | - Deduplication                           |
                           | - Risk scoring                            |
                           +---------------------+---------------------+
                                                 |
                                                 v
                           +---------------------+---------------------+
                           | Human Review and Moderation Layer          |
                           | - Review queue                             |
                           | - Analyst/admin approval                   |
                           | - Duplicate merge                          |
                           | - Verification workflow                    |
                           +---------------------+---------------------+
                                                 |
                                                 v
+-------------------+      +---------------------+---------------------+      +----------------+
| Web/Admin Clients | ---> | FastAPI Application Layer                  | ---> | Notifications  |
+-------------------+      | - REST APIs                                |      +----------------+
                           | - Auth and RBAC                            |
                           | - Feed, map, dashboard, watchlist APIs     |
                           +---------------------+---------------------+
                                                 |
                       +-------------------------+-------------------------+
                       |                                                   |
                       v                                                   v
              +----------------+                                  +----------------+
              | PostgreSQL     |                                  | Redis          |
              | - Events       |                                  | - Cache        |
              | - Sources      |                                  | - Job locks    |
              | - Raw data     |                                  | - Rate limits  |
              | - Audit logs   |                                  | - Coordination |
              +----------------+                                  +----------------+
```

## 6. Major Backend Subsystems

| Subsystem | Responsibility |
| --- | --- |
| API Gateway/Application Layer | FastAPI routes, request validation, response serialization, auth dependencies, role checks, rate-limit hooks. |
| Authentication and Authorization | JWT access tokens, refresh tokens, password hashing, user roles, permission matrix, protected admin/analyst routes. |
| Source Management | Create, update, disable, test, and score external sources. |
| GeoAtlas Source Console | Minimal internal UI that posts feed URLs to the backend, shows detected feed metadata, starts manual ingestion, and previews normalized output. |
| Ingestion Scheduler | Runs recurring source fetches, prevents concurrent source jobs, tracks job status, supports manual triggers. |
| Connector Layer | Source-specific fetchers for RSS, news APIs, datasets, government alerts, and manual submissions. |
| Raw Data Store | Stores original fetched payloads with source metadata and hashes for traceability. |
| Normalization Layer | Converts heterogeneous source records into common normalized items. |
| Event Extraction Layer | Extracts event candidates, categories, dates, actors, descriptions, and locations. |
| AI Assistance Layer | Produces structured suggestions and stores them for review; never publishes directly. |
| Deduplication Layer | Finds possible duplicate events using hashes, source URLs, text similarity, time windows, and geospatial proximity. |
| Risk Scoring Layer | Assigns suggested risk level and score using rule-based factors and confidence inputs. |
| Review Queue | Routes pending events, duplicate candidates, risk changes, and AI suggestions to analysts/admins. |
| Output API Layer | Exposes normalized items, extracted event candidates, approved events, map markers, job status, and JSON exports through versioned public endpoints. |
| Dashboard and Map Layer | Serves aggregate statistics, markers, country counts, bounding-box results, and high-risk alerts. |
| Watchlist Layer | Lets users track countries, categories, keywords, actors, and events. |
| Audit and Logging Layer | Records immutable user, admin, ingestion, AI, source, verification, and event changes. |
| Notification Layer | Sends user and admin notifications for watchlist matches, high-risk alerts, and ingestion failures. |

## 7. Key Data Domains

| Domain | Description |
| --- | --- |
| Identity | Users, roles, permissions, refresh tokens, account status. |
| Source Configuration | External sources, connector type, reliability score, fetch interval, rate limit, credentials reference. |
| Ingestion | Jobs, logs, raw fetched items, normalized items, processing status. |
| Event Intelligence | Events, categories, tags, sources, timelines, locations, verification status, risk score. |
| Review and Moderation | Review queue items, duplicate candidates, analyst/admin decisions. |
| AI Suggestions | Structured AI output, confidence, model, prompt version, human approval/rejection. |
| User Personalization | Watchlists, saved events, notifications. |
| Operational Audit | Immutable audit logs for security and compliance. |

## 8. Core Data Flow

### Automated Event Ingestion

```text
Scheduler starts source job
  -> Connector fetches source data
  -> Raw item is saved with hash and source metadata
  -> Duplicate raw items are skipped
  -> Normalizer creates normalized item
  -> Event extraction creates candidate event
  -> AI suggestions are generated when required
  -> Deduplication finds possible existing matches
  -> Risk scoring suggests severity
  -> Verification service suggests status
  -> Pending event enters review queue
  -> Analyst/admin approves, edits, rejects, or merges
  -> Approved event becomes visible in feed, map, dashboard, and watchlists
```

### Manual Event Creation

```text
Analyst/admin submits event
  -> API validates role and payload
  -> Event is created as pending review or published based on role policy
  -> Sources, locations, tags, and timeline entries are linked
  -> Risk and verification checks run
  -> Audit log is written
```

### Live Feed Read

```text
Client requests feed
  -> Optional auth context is resolved
  -> Filters and pagination are validated
  -> Cache is checked for common query shapes
  -> PostgreSQL returns published events
  -> Response includes event summary, risk, verification, location, and source count
```

### Map Read

```text
Client requests map markers or bounding box
  -> API validates coordinates and filters
  -> Map service queries location-optimized event data
  -> Redis/cache may serve common global or country views
  -> Compact marker response is returned
```

## 9. Technology Choices

| Concern | Choice | Reason |
| --- | --- | --- |
| Language | Python | Mature backend ecosystem, AI integration support, data processing libraries. |
| Web framework | FastAPI | Typed APIs, OpenAPI generation, async support, dependency injection. |
| Database | PostgreSQL | Strong relational model, indexes, JSONB, full-text search, PostGIS path. |
| Hosted database | Supabase Postgres + PostGIS | Managed PostgreSQL with PostGIS, backups, connection pooling, SQL editor, and optional RLS for public read surfaces. |
| ORM | SQLAlchemy | Production-grade ORM and query control. |
| Migrations | Alembic | Standard SQLAlchemy migration tooling. |
| Cache/coordination | Redis | Fast cache, rate limits, distributed locks, scheduler coordination. |
| Scheduler | APScheduler initially | Simple production fit for interval-based source ingestion. |
| Background execution | Dedicated scheduler/worker process | Keeps ingestion work out of request latency. |
| Authentication | JWT access tokens plus refresh tokens | Stateless API auth with controlled session rotation. |
| Process runtime | Gunicorn with Uvicorn workers | Stable production serving model for FastAPI. |
| Reverse proxy | Nginx | HTTPS termination, proxy buffering, request limits, static operational controls. |

## 10. Integration Architecture

### External Source Integration

| Source Type | Integration Pattern |
| --- | --- |
| RSS/Atom | Poll feed, respect ETag/Last-Modified, parse entries, hash content. |
| News APIs | Authenticated API calls, pagination, provider rate-limit handling, source-specific normalizer. |
| Public datasets | Scheduled fetch or incremental download, batch processing, dataset version tracking. |
| Government alerts | Official feed/API polling with high reliability defaults and strict provenance capture. |
| NGO reports | Feed/API/document metadata processing, source reliability scoring. |
| Manual input | Analyst/admin-created raw item with explicit provenance and audit trail. |

### GeoAtlas Data Collection Service Boundary

The first standalone service slice is the GeoAtlas data collection API. It can live inside GeoAtlas during development but must be packageable as an independent public API service later.

```text
GeoAtlas Feed UI
  -> POST feed URL
  -> Backend validates URL and blocks unsafe networks
  -> Backend auto-detects RSS/Atom metadata
  -> Source is saved in Supabase Postgres
  -> Scheduler/manual trigger fetches entries
  -> Backend extracts article content, language, locations, categories, and event candidates
  -> Normalized records and geospatial hints are stored
  -> Public API exposes JSON output and exports
```

Boundaries:

| Boundary | Design |
| --- | --- |
| Frontend responsibility | Only manage data collection sources: add RSS links, test detection, enable/disable feeds, trigger ingestion, and preview output. |
| Backend responsibility | Own feed validation, SSRF protection, content fetching, content extraction, normalization, geocoding hints, persistence, and public output APIs. |
| Public output | Expose read-only JSON endpoints for normalized feed items, extracted event candidates, approved events, job status, and optional export files. |
| Database access | API service talks to Supabase using server-side credentials; clients do not receive service-role keys. |
| Standalone deployment | The service keeps its own `/api/v1/sources`, `/api/v1/ingestion`, `/api/v1/public/*`, health, OpenAPI, migrations, and environment config. |
| News display UI | Not required; consumers use API responses, export endpoints, or their own frontend. |

Core GeoAtlas data collection routes:

| Route | Audience | Purpose |
| --- | --- | --- |
| `POST /api/v1/sources/rss` | Admin UI | Add a feed URL and save detected feed metadata. |
| `POST /api/v1/sources/detect` | Admin UI | Validate a URL and return feed/site metadata without saving. |
| `POST /api/v1/sources/{source_id}/ingest` | Admin UI/Ops | Trigger immediate ingestion and return a job id. |
| `GET /api/v1/ingestion/jobs/{job_id}` | Admin UI/Ops | Read ingestion counters, errors, and latest status. |
| `GET /api/v1/public/items` | Public/API users | Return normalized fetched items with source and extraction metadata. |
| `GET /api/v1/public/events` | Public/API users | Return approved or API-visible event records. |
| `GET /api/v1/public/export.json` | Public/API users | Download filtered output as JSON for external consumers. |

### AI Integration

AI is accessed through an internal `AIService`, not directly from route handlers or connectors.

```text
Event/Normalized text
  -> AIService
  -> Prompt safety and schema selection
  -> AI provider call
  -> Response validation
  -> ai_suggestions persistence
  -> Human review
```

AI failure does not block raw data preservation. It may block AI-enhanced extraction if the task requires AI-only output, but the event remains reviewable with lower confidence.

## 11. Security Architecture

| Area | High Level Control |
| --- | --- |
| Identity | Email/password login, strong password hashing, refresh token rotation. |
| API access | JWT middleware and role/permission dependencies. |
| Admin protection | Admin routes require elevated roles and write audit records. |
| External fetching | URL validation, private network blocking, redirect validation, timeout limits, source allow rules. |
| Rate limiting | Redis-backed limits for login, AI, source testing, and manual ingestion. |
| Secrets | API keys and tokens stored outside source code using environment or managed secret references. |
| Data integrity | Database constraints, transaction boundaries, immutable audit logs. |
| Input safety | Pydantic validation, length limits, enum constraints, SQLAlchemy parameter binding. |
| CORS | Explicit frontend origins per environment. |
| Observability | Request id, structured logs, ingestion logs, audit logs, health checks. |

## 12. Deployment Architecture

GeoAtlas is deployed on a standard server, cloud VM, or PaaS using a Python runtime, process manager, and reverse proxy.

```text
Internet
  |
  v
Nginx Reverse Proxy
  |-- HTTPS termination
  |-- API proxy
  |-- Request limits
  |
  v
Gunicorn + Uvicorn Workers
  |-- FastAPI application
  |-- REST APIs
  |
  +--------------------+
  |                    |
  v                    v
PostgreSQL           Redis
  |-- Data             |-- Cache
  |-- Migrations       |-- Locks
  |-- Backups          |-- Rate limits

Separate service process:
  APScheduler / ingestion worker
    -> source jobs
    -> connector execution
    -> normalization and review queue insertion
```

Runtime services:

| Service | Responsibility |
| --- | --- |
| `geo-atlas-api` | FastAPI application served through Gunicorn/Uvicorn. |
| `geo-atlas-scheduler` | APScheduler process for recurring ingestion jobs. |
| PostgreSQL | Primary relational data store. |
| Redis | Cache, locks, rate-limit counters, background coordination. |
| Nginx | HTTPS, reverse proxy, request limits, upstream routing. |

## 13. Scalability Strategy

| Scaling Area | Strategy |
| --- | --- |
| API traffic | Add more Gunicorn/Uvicorn workers; scale server size or PaaS instances. |
| Database reads | Add proper indexes, optimize projections, cache common feed/dashboard/map queries. |
| Map endpoints | Return compact markers, support bounding-box filters, cache global/country views. |
| Dashboard | Precompute aggregates and cache results. |
| Ingestion | Stagger source schedules, rate-limit per source, use locks to prevent overlap. |
| Large source payloads | Batch inserts, stream downloads where possible, process incrementally. |
| AI calls | Queue or throttle AI tasks, cache input-hash suggestions, retry with backoff. |
| Deduplication | Use cheap hashes first, then text/time/location similarity only for candidates. |

## 14. Availability And Reliability

| Concern | Design |
| --- | --- |
| Health checks | `/health` verifies API process, database, Redis, and scheduler heartbeat. |
| Graceful failure | Source or AI failures do not bring down read APIs. |
| Retry policy | Transient connector failures use exponential backoff and final failure logs. |
| Job locking | Per-source locks avoid concurrent duplicate ingestion runs. |
| Auditability | Raw items, AI suggestions, review actions, and event changes are preserved. |
| Backups | Scheduled PostgreSQL backups and restore checks. |
| Rollback | Release directories or deploy revisions allow code rollback; migration rollback strategy is planned per release. |
| Monitoring | Track API latency, error rate, ingestion failure rate, queue age, scheduler heartbeat, database health. |

## 15. Data Consistency Strategy

| Area | Strategy |
| --- | --- |
| Raw item deduplication | Unique source item id and content hash constraints. |
| Event publication | Event becomes public only after human review transaction succeeds. |
| Review decisions | Review status, event state change, and audit log are written in one transaction. |
| Risk changes | Risk update includes score, level, reason, actor, and audit entry. |
| Verification changes | Verification update includes before/after state and reviewer reason. |
| AI suggestions | Stored separately from canonical event fields until approved. |
| Soft deletion | Events are archived instead of physically deleted in normal workflows. |

## 16. Observability

| Signal | Purpose |
| --- | --- |
| Request logs | API usage, latency, failures, actor identity, request id. |
| Application logs | Service errors, warning conditions, external integration issues. |
| Ingestion logs | Source job lifecycle, fetched counts, duplicate counts, parser failures, retry attempts. |
| Audit logs | Immutable admin, analyst, user, source, event, risk, and verification actions. |
| Metrics | Latency, error rate, job duration, queue depth, AI failure rate, source success rate. |
| Alerts | Scheduler stalled, repeated source failures, high API error rate, database/Redis unavailable. |

## 17. Non-Functional Requirements

| Requirement | Target |
| --- | --- |
| API latency | Common feed/map/dashboard reads should respond within acceptable interactive latency under normal load. |
| Ingestion traceability | Every fetched item must be traceable to source, job, raw payload, normalized item, and review outcome. |
| Security | Admin and analyst operations require authenticated RBAC and audit logging. |
| Data durability | PostgreSQL is the source of truth; backups are mandatory. |
| Extensibility | New source connectors and AI providers can be added without rewriting core event workflows. |
| Maintainability | Layered architecture keeps routes, services, repositories, connectors, and AI logic separate. |
| Compliance readiness | Audit logs are immutable at application level and preserve actor/action/context. |

## 18. Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| False or misleading source reports | Human review, source reliability scoring, verification statuses, disputed/false retention. |
| AI hallucination | Structured schema validation, confidence scores, no direct publication, human approval. |
| External source outages | Retry policy, ingestion logs, source health monitoring, admin notifications. |
| Duplicate event flooding | Raw hash checks, deduplication candidates, merge workflow. |
| Slow map queries | Location indexes, compact marker DTOs, bounding-box filtering, cache. |
| Credential leakage | Secret references, environment-managed secrets, no secrets in source config responses. |
| SSRF through source URLs | URL safety validation, blocked private networks, redirect validation, timeout enforcement. |
| Review backlog growth | Priority queue, dashboard stats, manual assignment, high-risk prioritization. |

## 19. Release And Operations Plan

Recommended release phases:

1. Foundation: FastAPI app, PostgreSQL, migrations, auth, roles, logging, health checks.
2. Event core: categories, events, locations, sources, published feed, map markers.
3. Source ingestion: source management, RSS connector, ingestion jobs, raw storage, normalization.
4. Review workflow: pending events, approval, rejection, edit-before-approval, audit logs.
5. Risk and verification: scoring, verification transitions, review history.
6. Dashboards and watchlists: aggregate APIs, saved events, watchlist matching.
7. More connectors: news APIs, datasets, government alerts, manual source input.
8. AI suggestions: extraction, summary, risk, duplicate, location, timeline suggestions.
9. Production hardening: rate limits, monitoring, backups, rollback, security review.

Operational checklist:

```text
Provision PostgreSQL
Provision Redis
Configure production environment variables
Run migrations
Create superadmin
Start API service
Start scheduler service
Configure Nginx and HTTPS
Verify health endpoint
Verify login and RBAC
Verify source test and manual ingestion
Verify review approval flow
Verify feed, map, dashboard, and watchlist APIs
Enable backups and monitoring
Document rollback procedure
```

## 20. HLD Summary

GeoAtlas uses a layered FastAPI backend with PostgreSQL as the source of truth and Redis for cache, locks, rate limits, and coordination. Automated ingestion is a first-class subsystem: external sources are fetched by scheduled connector jobs, raw payloads are preserved, normalized records are processed into event candidates, and AI may provide structured suggestions. The system protects correctness by requiring analyst/admin review before publication.

Published events power the live feed, map, dashboard, watchlist, and cluster experiences. The architecture prioritizes traceability, security, operational clarity, extensibility, and production deployment on standard server, VM, or PaaS infrastructure.
