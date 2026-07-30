# src/routers — FastAPI routers

## Purpose

HTTP handlers mounted under `/v1` by `src/main.py`. Each router owns request parsing, dependency wiring, and orchestration; heavy logic lives in `src/service.py`, `src/billing.py`, and `src/clients/`.

## Ownership

- `optimization.py` (`/v1/optimization`) — `GET /fuel-types` (Redis-cached + ETag/304), `POST /on-route`, `POST /detailed-routes`, `POST /nearby`.
- `auth.py` (`/v1/auth`, tag `Auth`) — `POST /auth/google`: verifies Google ID token, creates user + default subscription if new, issues JWT.
- `subscriptions.py` (`/v1`, tag `Subscriptions`) — `GET /users/me/subscription`, `POST /billing/verify/google`, `POST /billing/webhook/google`.

## Local Contracts

- Auth-protected endpoints depend on `get_current_user_id` (JWT Bearer). Public endpoints (webhook, `auth/google`) do not.
- `on-route` flow: Mapbox route → PostGIS station fetch → `TypeAdapter` row→schema → parallel OSRM matrices + fuel-price merge → metrics → per-segment/per-network top-N.
- `nearby` flow: Mapbox isochrone polygon → PostGIS `ST_Intersects` → matrices + prices → per-network top-N.
- `verify/google`: idempotent on `purchase_token`; rejects tokens owned by another user with 403; verify→acknowledge→extract→upsert subscription + log history in one transaction (`commit`/`rollback`).
- `webhook/google`: HMAC-verify `x-goog-signature` → decode Pub/Sub envelope → map RTDN notification to status → update + log history; unknown/informational notifications return `{"status":"ignored",...}` with 200.

## Work Guidance

- Keep routers thin: delegate to `service.py` / `billing.py` / repositories.
- Use `Logger` (static) for router-level logs; repos/clients use `LoggerMixin`.
- New protected endpoint → depend on `get_current_user_id`.

## Verification

- Manual via running app (`uv run python -m src.main`) and hitting `/docs`.

## Child DOX Index

None.
