# src/clients — external HTTP clients

## Purpose

Thin async wrappers around external HTTP APIs used by the API and billing flows. All take an injected `httpx.AsyncClient`.

## Ownership

- `base.py` — `BaseRoutingClient` (`LoggerMixin`): shared coordinate-string/matrix-param builders and `_execute_get` (raises on `HTTPStatusError`/`RequestError`/JSON decode failure).
- `mapbox.py` — `MapboxClient`: directions, matrix, isochrones. Appends `access_token` (from `MAPBOX_API_KEY`) and an `approaches` string. Endpoints fixed as class attrs.
- `osrm.py` — `OsrmClient`: OSRM `table` and `route` endpoints at `http://osrm:5000/...` (Docker service name). No auth.
- `google_play.py` — `GooglePlayClient`: JWT-bearer auth flow against Google token URI using the service-account key, cached access token with 60s safety margin; `verify_purchase_token` + `acknowledge_purchase` against the Android Publisher v3 API. Module-level SA fields parsed eagerly from `GOOGLE_PLAY_SERVICE_ACCOUNT_KEY` (raises at import if required fields missing).

## Local Contracts

- Routing clients subclass `BaseRoutingClient`; matrix calls go through `_call_matrix` which builds `[anchor] + coordinates` and forwards/backward indices per `MatrixDirection`.
- OSRM matrix is computed as forward (start→stations) + backward (stations→end) and summed by the service layer — OSRM table does not support true many-to-many here.
- `GooglePlayClient` does **not** subclass `BaseRoutingClient`; it owns its own auth but still takes the shared `httpx.AsyncClient`.
- Do not instantiate clients with their own `httpx.AsyncClient` in request scope — use `Depends(get_httpx_client)`.

## Work Guidance

- Add new endpoint URLs as class attributes, not inline literals.
- Keep clients stateless except for auth-token caching.

## Verification

- Endpoints are exercised by the optimization and subscription router flows; no isolated client tests exist.

## Child DOX Index

None.
