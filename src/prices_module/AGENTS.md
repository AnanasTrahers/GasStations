# src/prices_module — fuel-price ETL subsystem

## Purpose

Scrapes per-network fuel prices from external Ukrainian sites, normalizes them into `FuelPriceRecord`, and bulk-upserts them into `fuel_prices`. Driven by Airflow DAGs in `dags/`; also runnable standalone.

## Ownership

- `enums.py` — `FuelTypeEnum`, `RegionEnum` (shared vocabulary across scrapers and mappers).
- `schemas.py` — `FuelPriceRecord`: the single normalized shape every scraper emits (`network_name`, `fuel_type`, `price` Decimal, `source`, `created_at`, `region`).
- `mappers.py` — `VseazsMapper` (enum→numeric IDs) and `MinfinMapper` (enum↔Ukrainian labels, ordered pattern list).
- `dal.py` — `BaseDAL`, `NetworkDAL` (bulk upsert `on_conflict_do_nothing` on `name`), `PricesDAL.insert` (upserts networks first, then bulk-upserts `FuelPrice` keyed on `(source, fuel_type, network_id, created_at)`, updating `price` on conflict).
- `settings.py` — `ScrapersSettings` singleton: user agent, timeouts, retry config, `VSEAZS_LIMITER` semaphore (4), shared `PARSERS_THREAD_EXECUTOR` (4 workers).
- `utils.py` — `run_parser` (offloads CPU-bound parsing to the thread pool, copying context) and tenacity log hooks.
- `scrapers/` — site-specific scrapers (own child doc).

## Local Contracts

- Every scraper subclasses `BaseScraper`, sets `SOURCE` and `BASE_URL`, and implements `collect(*, region, date_=None) -> list[FuelPriceRecord]`. Each is an async context manager.
- All scrapers output `FuelPriceRecord` only — no source-specific types cross the boundary into `dal.py` or DAGs.
- Upsert key `(source, fuel_type, network_id, created_at)` is the contract with the DB; changing it requires a migration.
- Parsing must run through `run_parser` to avoid blocking the event loop.

## Work Guidance

- Adding a source: new scraper in `scrapers/`, a mapper if enum translation is needed, add an extract task in the DAG.
- Do not create alias variables for `scraper_settings` members (per repo-wide rule).

## Verification

- Each scraper has a `__main__` block for standalone manual runs (`uv run python -m src.prices_module.scrapers.<name>`).
- DAG `fuel_prices_etl` end-to-end via `uv run --env-file .env airflow standalone`.

## Child DOX Index

- `scrapers/` — site scrapers (`base`, `minfin`, `vseazs`).
