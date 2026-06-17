# GeoAtlas Work Documentation

This file is the running work log for GeoAtlas. Anyone who works on the project should add an entry here describing what they changed, why they changed it, how they verified it, and what remains.

Technical reference documents:

| Document | Purpose |
| --- | --- |
| [README.md](README.md) | Backend low-level design and overall module plan. |
| [HLD.md](HLD.md) | High-level backend architecture and system context. |
| [docs/GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md](docs/GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md) | Runnable GeoAtlas data collection implementation notes. |
| [backend/db/geoatlas_data_collection_schema.sql](backend/db/geoatlas_data_collection_schema.sql) | Supabase Postgres + PostGIS schema for the data collection service. |

## How To Add An Entry

Add new entries at the top of the Work Log section.

Use this format:

```md
### YYYY-MM-DD - Short Title

**Developer:** Name

**Goal:** What you were trying to build or fix.

**What changed:**
- File or module changed: short explanation.
- File or module changed: short explanation.

**How to run or verify:**
- Command, endpoint, UI path, or manual check.

**Output or result:**
- What worked after the change.

**Known issues or follow-ups:**
- Anything not finished, risky, or planned next.
```

## Work Log

### 2026-06-17 - Detected Time Zone Display

**Developer:** Ahan

**Goal:** Translate displayed timestamps in the GeoAtlas Source Console into the browser-detected time zone.

**What changed:**
- `backend/static/index.html`: Added a visible detected time-zone status chip in the top toolbar.
- `backend/static/app.js`: Added browser time-zone detection, localized timestamp formatting, and recursive timestamp conversion for JSON output preview fields.

**How to run or verify:**
- Open `http://127.0.0.1:8000`.
- Confirm the top toolbar shows the detected time zone.
- Check source cards, detected sample items, and JSON output preview timestamps.

**Output or result:**
- The UI detected `Asia/Calcutta` in the current browser session.
- Output preview timestamps are displayed with `GMT+5:30`.
- Browser console showed no errors after reload.

**Known issues or follow-ups:**
- Add a manual time-zone override if analysts need to inspect output in another time zone.

### 2026-06-17 - Source Console UI And Functionality Pass

**Developer:** Ahan

**Goal:** Improve the GeoAtlas Source Console so adding feeds, loading sources, triggering ingestion, and reading output are clearer and less brittle.

**What changed:**
- `backend/static/index.html`: Added API docs link, message bar, admin-key visibility toggle, generated-key hint, clear button, source search/status filters, output source selector, copy-output button, and output summary.
- `backend/static/styles.css`: Added layout and state styles for the new controls, notices, toolbars, selected candidates, danger actions, and mobile behavior.
- `backend/static/app.js`: Reworked UI state management for admin-key loading, source filtering, selectable feed candidates, save/run/archive/view actions, scoped output refresh, JSON copy, and clearer error/success messages.

**How to run or verify:**
- Start the API from `backend` with `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- Open `http://127.0.0.1:8000`.
- Paste a generated admin key and refresh sources.
- Detect an RSS feed, save it, run ingestion, and confirm output JSON updates.
- Reload the page and check browser console errors.

**Output or result:**
- UI loads with `geoatlas-data-collection: DB ok`.
- Admin key loads protected source data from Supabase.
- RSS detection displays selectable candidates and sample items.
- Saving a source, running ingestion, and scoped output preview work from the UI.
- Browser console showed no errors after reload.

**Known issues or follow-ups:**
- Add a dedicated admin-key management screen if key rotation needs to happen from the browser.
- Add pagination or cursor controls once source/output volume grows.

### 2026-06-17 - Backend Folder And Database Admin Keys

**Developer:** Ahan

**Goal:** Move backend code into a dedicated `backend/` folder and replace the fixed environment admin key with generated admin keys stored in Supabase/Postgres.

**What changed:**
- `backend/`: Moved the FastAPI app, static source console, schema SQL, requirements, and local environment example into the backend folder.
- `backend/app/admin_keys.py`: Added admin key generation, hashing, storage, and validation helpers.
- `backend/app/models.py`: Added the `admin_api_keys` model.
- `backend/app/main.py`: Changed admin route validation to check `X-Admin-Key` against active hashed keys in the database.
- `backend/scripts/generate_admin_key.py`: Added a script that generates a plaintext key, stores only its hash in Supabase/Postgres, and prints the plaintext once.
- `backend/db/geoatlas_data_collection_schema.sql`: Added the `admin_api_keys` table and active-key index.
- `backend/static/index.html`: Updated the Admin key placeholder to refer to generated GeoAtlas admin keys.
- `.gitignore`: Updated ignores for backend-local `.env` and SQLite files.
- `docs/GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md`: Documented the new backend folder layout and admin key generation flow.

**How to run or verify:**
- Run `cd backend`.
- Run `python scripts/generate_admin_key.py --name local-admin`.
- Start the API with `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- Paste the generated key into the GeoAtlas Source Console admin key field.
- Call an admin endpoint such as `GET /api/v1/sources` with `X-Admin-Key`.

**Output or result:**
- Admin keys are now database-backed and can be rotated by generating a new key.
- The backend is now contained in the `backend/` folder.
- `admin_api_keys` exists in Supabase/Postgres and has one active generated key.
- A valid generated key successfully authenticated `GET /api/v1/sources`.
- An invalid key was rejected with HTTP 401.

**Known issues or follow-ups:**
- Add an admin-only key revocation/listing endpoint if key management needs to happen through the UI.
- Add role/scope support if multiple admin key permission levels are needed.

### 2026-06-17 - Supabase Pooler Connection

**Developer:** Ahan

**Goal:** Replace the unreachable direct Supabase Postgres URL with the IPv4-compatible Supabase pooler URI and verify GeoAtlas can use Supabase Postgres.

**What changed:**
- `backend/.env`: Updated `DATABASE_URL` to use the Supabase pooler host. This file is ignored by git and must not be committed.
- Supabase Postgres: GeoAtlas startup created or verified the core data collection tables.
- Supabase Postgres: Applied `backend/db/geoatlas_data_collection_schema.sql` to enable the full table/index shape for the data collection service.

**How to run or verify:**
- Run a SQLAlchemy connection check against `DATABASE_URL`.
- Restart the API with `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- Call `GET /health`.
- Query `information_schema.tables` for core GeoAtlas data collection tables.
- Call `GET /api/v1/public/items`.

**Output or result:**
- SQLAlchemy connected to Supabase Postgres through the pooler.
- `/health` returned `status: ok` and `database: ok`.
- Core tables found: `external_sources`, `ingestion_jobs`, `ingestion_logs`, `raw_fetched_items`, `normalized_items`, `normalized_item_locations`, and `event_candidates`.
- Expected indexes were created, including trigram and PostGIS GIST indexes.
- Public items endpoint responded with an empty list from the connected database.

**Known issues or follow-ups:**
- Add a migration system before production changes accumulate.

### 2026-06-17 - Supabase Postgres URL Attempt

**Developer:** Ahan

**Goal:** Configure `DATABASE_URL` using the Supabase Postgres password and verify whether GeoAtlas can connect directly to Supabase Postgres.

**What changed:**
- `.env`: Set `DATABASE_URL` to the Supabase direct Postgres connection string using the local password. This file is ignored by git and must not be committed.
- `backend/app/main.py`: Moved database table creation into startup and made `/health` report database errors as degraded health instead of crashing the whole API.
- `docs/GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md`: Added a note about using the Supabase pooler connection string when direct IPv6 database access is not available.

**How to run or verify:**
- Restart the API with `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- Call `GET /health`.
- Test DNS and network access for the direct Supabase database host.

**Output or result:**
- Supabase API keys are configured and the API service starts.
- `DATABASE_URL` is configured as a Postgres URL.
- Direct DB connection failed from this machine because the Supabase direct database host resolves to IPv6 and the local network cannot reach that IPv6 address.
- `/health` now reports database status as `error` with service status `degraded` instead of letting the app crash on startup.

**Known issues or follow-ups:**
- Replace `DATABASE_URL` with the Supabase IPv4-compatible connection pooler URI from Project Settings -> Database -> Connection string.
- After the pooler URL is added, restart the API and recheck `/health` for `database: ok`.

### 2026-06-17 - Supabase Environment Wiring

**Developer:** Ahan

**Goal:** Add the Supabase project URL and API keys to the local runtime environment and make the backend aware of the Supabase configuration.

**What changed:**
- `.env`: Added `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` locally. This file is ignored by git and should not be committed.
- `backend/app/config.py`: Added Supabase URL, anon key, and service-role key settings.
- `backend/app/main.py`: Extended `/health` to report whether Supabase URL/API keys are configured without exposing secret values.
- `.env.example`: Added placeholder Supabase environment variables for future developers.
- `docs/GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md`: Documented the difference between Supabase API keys and the Postgres `DATABASE_URL`.

**How to run or verify:**
- Start the API with `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- Call `GET /health` and confirm Supabase settings show as configured.
- Set `DATABASE_URL` to the Supabase Postgres connection string when ready to store data in Supabase Postgres.

**Output or result:**
- Supabase project API settings are available to the backend through environment variables.
- Local `/health` reports Supabase URL, anon key, and service-role key as configured.
- Supabase REST root was reachable with the service-role key and returned HTTP 200.

**Known issues or follow-ups:**
- A real Supabase Postgres connection still requires the database password or full pooled connection string in `DATABASE_URL`.

### 2026-06-17 - GeoAtlas Data Collection First Build

**Developer:** Ahan

**Goal:** Build the first usable data collection slice for GeoAtlas where an internal user can add RSS/Atom feed links, let the backend auto-detect feed content, ingest entries, store output, and expose public API output without building a public news frontend.

**What changed:**
- `backend/app/main.py`: Added FastAPI routes for feed detection, source CRUD, manual ingestion, job lookup, public items, public events, public sources, JSON export, health, OpenAPI, and the internal source console.
- `backend/app/feed_utils.py`: Added RSS/Atom fetching, URL safety checks, private-network blocking, XML parsing, HTML feed discovery, item hashing, simple category hints, and simple location hints.
- `backend/app/services.py`: Added source detection, source creation, synchronous manual ingestion, raw item storage, normalized item creation, and event candidate creation.
- `backend/app/models.py`: Added SQLAlchemy models for sources, ingestion jobs, raw fetched items, normalized items, and event candidates.
- `backend/app/schemas.py`: Added Pydantic request and response models for admin APIs and public output APIs.
- `backend/static/index.html`, `backend/static/styles.css`, `backend/static/app.js`: Added the internal GeoAtlas Source Console for adding feeds, detecting metadata, saving sources, triggering ingestion, and previewing public JSON output.
- `backend/db/geoatlas_data_collection_schema.sql`: Added Supabase Postgres + PostGIS SQL schema and indexes for the data collection slice.
- `backend/.env.example`: Added GeoAtlas runtime environment variables.
- `backend/requirements.txt`: Added Python dependencies for the FastAPI service.
- `.gitignore`: Added local environment, cache, and SQLite database ignores.
- `docs/GEOATLAS_DATA_COLLECTION_IMPLEMENTATION.md`: Added run instructions, endpoint list, Supabase setup notes, admin key notes, public output contract, and current limits.
- `README.md`, `HLD.md`: Linked the runnable implementation notes and aligned data collection language with GeoAtlas naming.

**How to run or verify:**
- Run `cd backend`.
- Install dependencies with `pip install -r requirements.txt`.
- Start the API with `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- Open `http://127.0.0.1:8000` to use the GeoAtlas Source Console.
- Check health with `GET /health`.
- Detect a feed with `POST /api/v1/sources/detect`.
- Add a feed with `POST /api/v1/sources/rss`.
- Trigger ingestion with `POST /api/v1/sources/{source_id}/ingest`.
- Read output with `GET /api/v1/public/items` or `GET /api/v1/public/export.json`.

**Output or result:**
- Local API health returned `{"status":"ok","database":"ok","service":"geoatlas-data-collection"}`.
- Browser UI rendered as `GeoAtlas Source Console`.
- RSS detection was verified with NASA's RSS feed.
- Manual ingestion produced normalized public items and event candidates.

**Known issues or follow-ups:**
- Manual ingestion currently runs synchronously inside the API request; move it to a scheduler/worker for production.
- RSS parsing is dependency-light and should later be upgraded with stronger article extraction and feed compatibility.
- Location extraction is currently simple keyword matching; replace with a geocoder or NLP pipeline.
- Add automated tests around URL safety, feed detection, duplicate handling, and public output schemas.
