# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Facts
Every time you get new information about this project, or new way of interaction with 
library/models/services, or specific instructions from user on how to test/implement new feature,
add short description of acquired knowledge here in bulleted list:
- After work is done in worktrees - merge worktree branch into main locally (`git merge`); do NOT push worktree branches to remote; Delete worktree after successful merge;
- If needed DTO model - create pydantic schema in separate schemas.py file related to working module
- Never add anything to `__init__.py`. Use full-path imports.
- Don't create additional variables like `limiter = scraper_settings.VSEAZS_LIMITER`. If direct usage do not worsen readability of performance - use directly.
- `.agents/skills/<domain>/SKILL.md` files contain domain-specific agent guidance — always read the relevant skill before working in that area.
- Airflow metadata DB must be initialized once via `uv run airflow db migrate` (creates `~/airflow/airflow.db` with task_instance + other tables). Without this, importing `pipeline.py` fails with `OperationalError: no such table: task_instance`.
- `airflow_home/airflow_local_settings.py` adds the project root to `sys.path` so all Airflow subprocesses (scheduler, DAG processor, task runners) can resolve `src.*` imports. Airflow loads this file automatically at startup from `AIRFLOW_HOME` — prefer this over `PYTHONPATH` env var which task runner subprocesses may not inherit.

## Build/Run Commands

```bash
# Install deps (uv required)
uv sync

# Airflow DB init (one-time, creates ~/airflow/airflow.db)
uv run airflow db migrate

# Run dev server
uv run python -m src.main

# Docker (app + PostGIS)
docker compose up --build

# Alembic migrations
uv run alembic upgrade head            # apply all
uv run alembic revision --autogenerate -m "<msg>"  # new migration (reads src/models.py)
uv run alembic downgrade -1            # rollback one
```

No test suite exists yet.

## Architecture

**FastAPI** app optimizing gas station selection along driving routes. Uses PostGIS for spatial queries, Mapbox for directions, OSRM for distance/duration matrices.

### Data Flow (main endpoint `POST /v1/optimization/on-route`)

1. **Mapbox Directions** → get route geometry + distance + duration between start/end
2. **PostGIS spatial query** (`ST_DWithin` + `ST_LineLocatePoint`) → find stations within buffer radius of route, assign each a `fraction` (0–1 position along route)
3. **Segment assignment** → divide route into `SEGMENT_LENGTH_M` segments, bin stations by segment
4. **Fuel price lookup** → fetch latest price per network (within `FUEL_PRICE_SAFE_DAYS`), filter stations without pricing
5. **OSRM matrix** (forward + backward) → calculate total detour distance/duration for each station (start→station + station→end)
6. **Metrics** → compute distance/duration differences, fuel cost, total cost (fuel + extra distance fuel + lost income time)
7. **Ranking** → per segment+network, keep top `MAX_STATIONS_PET_NETWORK` stations sorted by total_price

### Layer Map

```
routers.py          — HTTP handlers, parameter extraction, orchestration
    ↓
service.py          — pure functions: spatial queries, matrix math, station metrics
    ↓
clients/*.py        — MapboxClient, OSRMClient (both extend BaseRoutingClient)
database.py         — async SQLAlchemy engine + session factory
models.py           — ORM models (Network, GasStation, FuelPrice)
schemas.py          — Pydantic request/response models + DirectionsParams dataclass
```

### Database

- All tables in **`app`** schema (PostGIS extension in `public`, topology in `topology`)
- `networks` — gas station brands
- `gas_stations` — points (GEOGRAPHY, SRID 4326), FK→networks
- `fuel_prices` — per-network fuel prices with `fuel_type` + `created_at`
- Alembic configured for async + GeoAlchemy2, filters to `app` schema only
- DB URL comes from `DATABASE_URL` env var; format: `postgresql+asyncpg://...`

### Clients

`BaseRoutingClient` provides coordinate-string building, matrix param construction, and shared `_execute_get`. Subclasses:
- **MapboxClient** — directions (turn-by-turn), matrix (distance/duration), isochrones. Requires API key appended as `access_token` query param.
- **OSRMClient** — table endpoint for many-to-many distance/duration matrices. No auth.

Both instantiated as `httpx.AsyncClient` in FastAPI lifespan, injected via `Depends(get_mapbox_client)` / `Depends(get_osrm_client)`.

### Key Design Decisions

- **Geography (not geometry)** for `gas_stations.geog` — spheroidal distance calculations via `ST_DWithin` work directly in meters
- **Forward + backward OSRM matrices** — computes start→station distance and station→end distance separately, then sums. OSRM table endpoint doesn't support many-to-many out of the box
- **ContextVar for request ID** — `LOG_ID` set by middleware, available anywhere in request scope via `get_log_id()`
- **Station.model_validator(mode="before")** — maps raw SQLAlchemy `Row` objects to pydantic model, so service layer returns DB rows directly and schemas handle conversion
- **DirectionsParams** is a dataclass (not BaseModel) — manual `asdict()` filtering for None values when passed as query params

### Logging

`LoggerMixin` (from `src/utils/logs.py`) provides `log_info`/`log_warning`/`log_error`. Prefixes messages with `[ClassName][methodName]`. `ContextVar LOG_ID` set by middleware enables request-scoped log correlation via `get_log_id()`.

### External API Endpoints Configured

| Setting | Purpose |
|---------|---------|
| `MAPBOX_DIRECTIONS_ENDPOINT` | Route geometry + turn-by-turn |
| `MAPBOX_MATRIX_ENDPOINT` | Distance/duration matrices |
| `MAPBOX_ISOCHRONE_ENDPOINT` | Reachability polygons (not used in routers yet) |
| `OSRM_TABLE_ENDPOINT` | Station detour matrices |