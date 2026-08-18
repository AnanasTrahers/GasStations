# src/prices_module — fuel-price ETL subsystem

## Purpose

Scrapes per-network fuel prices from external Ukrainian sites, normalizes them into `FuelPriceRecord`, and bulk-upserts them into `fuel_prices`. Also owns the canonical network name registry used across all ETL pipelines, the `OverpassScraper` for gas station location import, and the `StationDAL` for spatial upserts. Driven by the arq jobs in `src/worker/jobs.py`; also runnable standalone.

## Ownership

- `enums.py` — `FuelTypeEnum`, `RegionEnum` (shared vocabulary across scrapers and mappers).
- `schemas.py` — `FuelPriceRecord` (price scraper output) and `StationRecord` (Overpass station output).
- `mappers.py` — `VseazsMapper` (enum→numeric IDs) and `MinfinMapper` (enum↔Ukrainian labels, ordered pattern list).
- `network_registry.py` — canonical network name registry. Maps all known aliases (Cyrillic/Latin/case variants) to a single display name. `normalize_network_name(raw)` → canonical or raw + warning. `is_known_network(raw)` → bool (silent).
- `dal.py` — `BaseDAL`, `NetworkDAL` (bulk upsert `on_conflict_do_nothing` on `name`), `PricesDAL.insert` (upserts networks first, then bulk-upserts `FuelPrice`), `StationDAL.spatial_upsert` (same network + within 50m = update, else insert).
- `settings.py` — `ScrapersSettings` singleton: user agent, timeouts, retry config, `VSEAZS_LIMITER` semaphore (4), `PARSERS_THREAD_EXECUTOR` (4 workers), `OVERPASS_TIMEOUT` (240s).
- `utils.py` — `run_parser` (offloads CPU-bound parsing to the thread pool, copying context) and tenacity log hooks.
- `scrapers/` — site-specific scrapers (own child doc).

## Local Contracts

- Every price scraper subclasses `BaseScraper`, sets `SOURCE` and `BASE_URL`, and implements `collect(*, region, date_=None) -> list[FuelPriceRecord]`. The `OverpassScraper` implements `collect() -> list[StationRecord]` (no region/date). Each is an async context manager.
- All price scrapers output `FuelPriceRecord` only; `OverpassScraper` outputs `StationRecord` only — no source-specific types cross into DALs or jobs.
- Network names from scrapers must be normalised via `normalize_network_name()` in the job's transform step before reaching the DAL.
- Upsert key `(source, fuel_type, network_id, created_at)` is the price DB contract; `(network_id, geog proximity 50m)` is the station DB contract.
- Parsing must run through `run_parser` to avoid blocking the event loop.

## Work Guidance

- Adding a source: new scraper in `scrapers/`, a mapper if enum translation is needed, add an `_extract_*` helper to `src/worker/jobs.py` and gather it alongside the others.
- Do not create alias variables for `scraper_settings` members (per repo-wide rule).

## Verification

- Each scraper has a `__main__` block for standalone manual runs (`uv run python -m src.prices_module.scrapers.<name>`).
- `fuel_prices_etl` end-to-end via `uv run python -m src.worker.trigger fuel_prices_etl --now` (inline, no Redis needed).

## Child DOX Index

- `scrapers/` — site scrapers (`base`, `minfin`, `vseazs`, `overpass`).
