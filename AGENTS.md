# DOX framework

- DOX is highly performant AGENTS.md hierarchy installed here
- Agent must follow DOX instructions across any edits

## Project

GasStations — a FastAPI/SQLAlchemy service on PostGIS with two subsystems sharing one codebase and DB: (1) a route-optimization API that picks the cheapest gas stations along a driving route (Mapbox directions + PostGIS + OSRM matrices), and (2) a fuel-price ETL (`src/prices_module/`, orchestrated by Airflow in `dags/`) that scrapes Ukrainian fuel-price sites and bulk-upserts into `fuel_prices`. Python 3.13, `uv` for deps, Docker Compose for local infra (PostGIS, Redis, OSRM).

### Root-owned files

- `pyproject.toml` / `uv.lock` — dependency manifest and lock (uv).
- `Dockerfile` — app image; runs `uvicorn src.main:app` on `:8000`.
- `docker-compose.yml` — `db` (postgis), `redis`, `app`, `osrm-preprocessor`, `osrm`.
- `alembic.ini` — Alembic config (`script_location = migrations`, `prepend_sys_path = .`).
- `.env` — per-machine, gitignored; loaded only by `src/config.py` (and `airflow_local_settings.py` via dotenv). Airflow CLIs must run as `uv run --env-file .env airflow ...`.
- `CLAUDE.md` — legacy Claude Code guide; superseded by this DOX tree for agent work. Do not extend it; record new durable knowledge in the nearest AGENTS.md.

### Repo-wide rules

- Never add anything to `__init__.py`. Use full-path imports (`from src.x.y import z`).
- New DTO → pydantic schema in the relevant module's `schemas.py` (root `src/schemas.py` for the API, `src/prices_module/schemas.py` for ETL).
- Do not create alias variables for settings members (e.g. `limiter = scraper_settings.VSEAZS_LIMITER`); reference them directly unless readability/perf genuinely suffers.
- All tables live in the `app` schema (PostGIS ext in `public`, topology in `topology`); migrations target `app` only.
- Log only through `src/utils/logs.py` (`Logger` static or `LoggerMixin`); never bare `print`/stdlib `logging`.
- Geometry to PostGIS must be `WKTElement` SRID 4326 from `src/utils/wkt_builders.py`.
- No test suite exists yet; verification commands live in each child AGENTS.md.

## Core Contract

- AGENTS.md files are binding work contracts for their subtrees
- Work products, source materials, instructions, records, assets, and durable docs must stay understandable from the nearest applicable AGENTS.md plus every parent AGENTS.md above it

## Read Before Editing

1. Read the root AGENTS.md
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every AGENTS.md found along each route
5. If a parent AGENTS.md lists a child AGENTS.md whose scope contains the path, read that child and continue from there
6. Use the nearest AGENTS.md as the local contract and parent docs for repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no child doc may weaken DOX

Do not rely on memory. Re-read the applicable DOX chain in the current session before editing.

## Update After Editing

Every meaningful change requires a DOX pass before the task is done.

Update the closest owning AGENTS.md when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- user preferences about behavior, communication, process, organization, or quality
- AGENTS.md creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index changes. Update child docs when parent changes alter local rules. Remove stale or contradictory text immediately. Small edits that do not change behavior or contracts may leave docs unchanged, but the DOX pass still must happen.

## Hierarchy

- Root AGENTS.md is the DOX rail: project-wide instructions, global preferences, durable workflow rules, and the top-level Child DOX Index
- Child AGENTS.md files own domain-specific instructions and their own Child DOX Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be

## Child Doc Shape

- Create a child AGENTS.md when a folder becomes a durable boundary with its own purpose, rules, responsibilities, workflow, materials, or quality standards
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:
- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child DOX Index

## Style

- Keep docs concise, current, and operational
- Document stable contracts, not diary entries
- Put broad rules in parent docs and concrete details in child docs
- Prefer direct bullets with explicit names
- Do not duplicate rules across many files unless each scope needs a local version
- Delete stale notes instead of explaining history
- Trim obvious statements, repeated rules, misplaced detail, and warnings for risks that no longer exist

## Closeout

1. Re-check changed paths against the DOX chain
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child DOX Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why

## User Preferences

When the user requests a durable behavior change, record it here or in the relevant child AGENTS.md

- **Error Messages**: Backend endpoints should return error details in English, not Ukrainian.
- **Python Quality Standards**:
  - Prefer `pathlib` over `os.path` for all path manipulations.
  - Encapsulate module state in classes and use lazy initialization (e.g. `@classmethod` or properties) for heavy data loads (like loading GeoJSON or performing spatial operations) to avoid blocking main thread on import.
  - Catch specific exceptions (e.g., `FileNotFoundError`, `JSONDecodeError`) rather than generic `Exception`.

## Child DOX Index

- `src/` — importable application: FastAPI app, config, async DB, ORM models, schemas, repositories, service layer, DI, security, billing, seeder. Owns `clients/`, `routers/`, `utils/`, `prices_module/`.
  - `src/clients/` — external HTTP clients (Mapbox, OSRM, Google Play).
  - `src/routers/` — FastAPI routers mounted under `/v1` (optimization, auth, subscriptions).
  - `src/utils/` — shared utilities (logging, Redis cache, ETag, WKT builders, response helpers, billing/Pub-Sub helpers, datetime/uuid).
  - `src/prices_module/` — fuel-price ETL subsystem and station import (enums, schemas, mappers, network registry, DAL with spatial upsert, settings, utils).
    - `src/prices_module/scrapers/` — site scrapers (`base`, `minfin`, `vseazs`, `overpass`).
- `dags/` — Airflow ETL DAGs (`fuel_prices_etl` async, `fuel_prices_etl_sync` sync variant, `gas_stations_import` weekly station import from OSM).
- `migrations/` — async Alembic for the `app` schema (GeoAlchemy2-wired).
- `airflow_home/` — Airflow `$AIRFLOW_HOME`; `config/airflow_local_settings.py` bootstraps `sys.path` so DAGs import `src.*`.
- `osrm/` — OSRM Docker preprocessing entrypoint (download + extract + contract Ukraine OSM).