# src — application package

## Purpose

The importable application: FastAPI app, config, async DB engine/session, ORM models, pydantic schemas, repositories, service layer, dependency injection, security, billing logic, and the DB seeder. Owns the `clients/`, `routers/`, `utils/`, and `prices_module/` sub-packages.

## Ownership

- Direct files: `main.py`, `config.py`, `database.py`, `models.py`, `schemas.py`, `repositories.py`, `service.py`, `dependencies.py`, `security.py`, `billing.py`, `seeder.py`, `api/middleware.py`.
- Sub-packages (`clients/`, `routers/`, `utils/`, `prices_module/`) own their own contracts; see their AGENTS.md.

## Local Contracts

- `main.py` builds the `FastAPI` app, registers routers under `/v1`, adds `LogIdMiddleware`, and owns the lifespan that creates the shared `httpx.AsyncClient` + `redis.asyncio.Redis`. Exception handlers map `httpx.HTTPError`→502 and `OperationalError`→503.
- `config.py` — `ProjectSettings` (secrets/URLs from `.env`, `env_file=ROOT_DIR/.env`) and `BusinessSettings` (tunable business params with defaults). Module-level singletons `project_settings`, `business_settings`. `ROOT_DIR` is the repo root; `LOG_ID` ContextVar lives here.
- `database.py` — `Base` (DeclarativeBase with `MetaData(schema="app")`), async `engine` (`echo=True`, `search_path=app, public, topology`), `AsyncSessionLocal`, `get_db()` async generator dependency.
- `models.py` — the only place ORM models are defined: `Network`, `GasStation`, `FuelPrice`, `User`, `Subscription`, `SubscriptionHistory`. `gas_stations.geog` is GEOGRAPHY Point SRID 4326.
- `schemas.py` — pydantic request/response models + `DirectionsParams` dataclass. `BaseStation.model_validator(mode="before")` maps a SQLAlchemy `Row` to the schema. `SubscriptionStatus.grants_premium` encodes which states unlock premium.
- `repositories.py` — `DBRepository` facade aggregating `StationsRepository`, `PricesRepository`, `UsersRepository`, `SubscriptionsRepository`, each wrapping an `AsyncSession`. All inherit `LoggerMixin`.
- `service.py` — pure/async functions for route optimization: spatial station fetch merge, segment assignment, forward+backward OSRM matrix merge, metric calculation, per-network top-N ranking, Redis-backed fuel-type caching.
- `dependencies.py` — FastAPI `Depends` providers: `get_db_repo`, `get_httpx_client`, `get_redis`, `get_current_user_id` (JWT Bearer via `HTTPBearer`).
- `security.py` — `verify_google_token` (offloaded via `asyncio.to_thread`) and `create_access_token` (HS256 JWT, TTL from `business_settings.JWT_TTL_DAYS`).
- `billing.py` — Google Play mapping tables: RTDN `notificationType`→`SubscriptionStatus` and `subscriptionState`→`SubscriptionStatus`; `extract_subscription_data` builds the typed `SubscriptionData`.
- `seeder.py` — dev-only seed script (`drop_all`/`create_all` then inserts). Run via `__main__`, not in production.
- `api/middleware.py` — `LogIdMiddleware` sets `LOG_ID` per request and echoes `X-Request-ID`.

## Work Guidance

- New ORM model → add to `models.py`, then `uv run alembic revision --autogenerate`.
- New pydantic DTO → add to `schemas.py` (or the relevant module's `schemas.py` for `prices_module`).
- New endpoint → add a router file under `src/routers/` and register it in `main.py`.
- New external service → add a client under `src/clients/`; inject via `Depends(get_httpx_client)`.
- Business tuning knobs go in `BusinessSettings`, not hardcoded.

## Verification

- `uv run python -c "import src.main"` imports the app and wires all routers.
- `uv run python -m src.seeder` recreates and seeds a dev DB.

## Child DOX Index

- `clients/` — external HTTP clients.
- `routers/` — FastAPI routers.
- `utils/` — shared utilities.
- `prices_module/` — fuel-price ETL subsystem.
