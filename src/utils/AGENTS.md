# src/utils — shared utilities

## Purpose

Cross-cutting helpers used by the API, service layer, clients, scrapers, and DAGs: structured logging, request-scoped IDs, Redis cache, ETag, WKT geometry builders, response shape extractors, billing/Pub/Sub helpers, and datetime/uuid factories.

## Ownership

- `logs.py` — structlog configuration + `Logger` (static, `@inject_traceback` adds caller file/line) and `LoggerMixin` (class-based, prefixes `[ClassName]`). Both thread `LOG_ID` via `get_log_id()`. Uvicorn loggers silenced to WARNING.
- `order.py` — `get_datetime_utc`, `get_datetime_kyiv` (Europe/Kyiv), `get_uuid_str`, `get_log_id` (reads/sets `LOG_ID` ContextVar, defaulting to a fresh uuid).
- `redis.py` — `get_cached_fuel_types` / `set_cached_fuel_types` under key `fuel_types`, TTL `FUEL_TYPES_CACHE_TTL`.
- `etag.py` — `generate_etag` (md5 of str(data)) and `check_etag_match`.
- `wkt_builders.py` — `get_route_wkt` (LineString) and `get_polygon_wkt` (Polygon) → `WKTElement` SRID 4326, via shapely. Note the nesting differs: `get_route_wkt` takes a flat list of `[lng, lat]` points, while `get_polygon_wkt` takes GeoJSON *rings* (`[shell, *holes]`, one level deeper) exactly as `get_polygon` returns them from an isochrone response.
- `response_helpers.py` — safe extractors for Mapbox/OSRM JSON shapes (route coords/length/duration, matrix distances/durations, isochrone polygon); raise+log on missing keys.
- `billing.py` — `_verify_pubsub_signature` (HMAC-SHA256 over body vs `GOOGLE_PUBSUB_VERIFICATION_TOKEN`, constant-time compare) and `_decode_pubsub_payload` (base64+json decode of Pub/Sub `message.data`).
- `annotations.py` — type aliases (e.g. `StrUUID`).
- `geo_validation.py` — geospatial validation (`GeoValidator`) for points and routes using an import-time loaded, pre-computed WKB polygon. Fails fast if the asset is missing.

## Local Contracts

- Always log through `Logger`/`LoggerMixin`, never bare `print` or stdlib `logging`.
- `LOG_ID` is set per HTTP request by `LogIdMiddleware`; in DAG/offline code `get_log_id()` lazily creates one.
- Geometry handed to PostGIS must be a `WKTElement` SRID 4326 from `wkt_builders`.
- Pub/Sub signature verification must run before any payload parsing.

## Work Guidance

- Prefer adding a new extractor here over inline dict access in service/router code.

## Verification

- Exercised indirectly through API and ETL flows; no isolated tests.

## Child DOX Index

None.
