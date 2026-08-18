"""arq job coroutines for the fuel-price and gas-station ETLs.

Each pipeline is a single job that runs extract -> transform -> load in-process.
The stages used to be separate Airflow tasks, which forced every record through a
JSON round-trip over XCom; here they are plain function calls and records stay as
``FuelPriceRecord`` / ``StationRecord`` instances the whole way.

arq is pessimistic — a worker crash re-runs the job — so both pipelines must stay
idempotent. They are: ``PricesDAL.insert`` upserts on
``(source, fuel_type, network_id, created_at)`` and ``StationDAL.spatial_upsert``
matches existing rows by network + 50 m proximity.
"""

import asyncio

import httpx

from src.database import AsyncSessionLocal
from src.prices_module.dal import NetworkDAL, PricesDAL, StationDAL
from src.prices_module.enums import RegionEnum
from src.prices_module.network_registry import normalize_network_name
from src.prices_module.schemas import FuelPriceRecord, StationRecord
from src.prices_module.scrapers.minfin import MinfinScraper
from src.prices_module.scrapers.overpass import OverpassScraper
from src.prices_module.scrapers.vseazs import VseazsScraper
from src.utils.logs import Logger


# ── fuel prices ─────────────────────────────────────────────────────

async def _extract_minfin(
        client: httpx.AsyncClient, region: RegionEnum
) -> list[FuelPriceRecord]:
    Logger.info("[extract][minfin] starting", region=region.value)
    async with MinfinScraper(client=client) as scraper:
        records = await scraper.collect(region=region)
    Logger.info(
        "[extract][minfin] done", region=region.value, records=len(records)
    )
    return records


async def _extract_vseazs(
        client: httpx.AsyncClient, region: RegionEnum
) -> list[FuelPriceRecord]:
    Logger.info("[extract][vseazs] starting", region=region.value)
    async with VseazsScraper(client=client) as scraper:
        records = await scraper.collect(region=region)
    Logger.info(
        "[extract][vseazs] done", region=region.value, records=len(records)
    )
    return records


def _transform_prices(records: list[FuelPriceRecord]) -> list[FuelPriceRecord]:
    """Map each source's network label onto its canonical registry name."""
    Logger.info("[transform] starting", records=len(records))
    for record in records:
        record.network_name = normalize_network_name(record.network_name)
    Logger.info("[transform] done", total=len(records))
    return records


async def _load_prices(records: list[FuelPriceRecord]) -> None:
    Logger.info("[load] starting", records=len(records))
    async with AsyncSessionLocal() as db_session:
        await PricesDAL(db_session=db_session).insert(records)
        await db_session.commit()
    Logger.info("[load] done")


async def fuel_prices_etl(
        ctx: dict, region: str = RegionEnum.KYIV.value
) -> int:
    """Scrape minfin + vseazs prices for *region* and upsert them.

    Returns the number of records loaded.
    """
    region_ = RegionEnum(region)
    client: httpx.AsyncClient = ctx["httpx_client"]

    minfin_records, vseazs_records = await asyncio.gather(
        _extract_minfin(client, region_),
        _extract_vseazs(client, region_),
    )
    records = _transform_prices(minfin_records + vseazs_records)

    # PricesDAL.insert builds insert().values([]), which raises on an empty list.
    if not records:
        Logger.warning(
            "[fuel_prices_etl] nothing scraped, skipping load",
            region=region_.value,
        )
        return 0

    await _load_prices(records)
    return len(records)


# ── gas stations ────────────────────────────────────────────────────

def _dedupe_stations(records: list[StationRecord]) -> list[StationRecord]:
    """Deduplicate within the batch (same network + very close coords).

    Stations of the same network very close together are the same physical
    location mapped as multiple OSM nodes; keep only the first.

    Note: A grid-based approach can theoretically separate points that fall
    across grid boundaries, but boundary-split duplicates will be caught by
    the strict 50m proximity constraint in the DAL anyway.
    """
    Logger.info("[transform] starting", records=len(records))

    seen: dict[tuple[str, float, float], StationRecord] = {}
    for rec in records:
        # Round to ~11m grid (4 decimal places ~ 11m)
        grid_key = (rec.network_name, round(rec.lat, 4), round(rec.lng, 4))
        if grid_key not in seen:
            seen[grid_key] = rec

    deduped = list(seen.values())
    Logger.info(
        "[transform] done",
        before=len(records),
        after=len(deduped),
        removed=len(records) - len(deduped),
    )
    return deduped


async def gas_stations_import(ctx: dict) -> tuple[int, int]:
    """Import all branded Ukrainian fuel stations from Overpass/OSM.

    Returns ``(inserted, updated)`` counts.
    """
    client: httpx.AsyncClient = ctx["httpx_client"]

    Logger.info("[extract][overpass] starting")
    async with OverpassScraper(client=client) as scraper:
        raw_records = await scraper.collect()
    Logger.info("[extract][overpass] done", records=len(raw_records))

    stations = _dedupe_stations(raw_records)
    if not stations:
        Logger.warning("[gas_stations_import] nothing scraped, skipping load")
        return 0, 0

    Logger.info("[load] starting", records=len(stations))
    async with AsyncSessionLocal() as db_session:
        # Ensure all referenced networks exist.
        network_dal = NetworkDAL(db_session=db_session)
        await network_dal.upsert_bulk_network(
            data={s.network_name for s in stations}
        )
        network_map = await network_dal.get_all_network_map()

        # spatial_upsert uses a TEMP TABLE ... ON COMMIT DROP, so it has to stay
        # inside the same transaction as the commit below.
        inserted, updated = await StationDAL(
            db_session=db_session
        ).spatial_upsert(data=stations, network_map=network_map)
        await db_session.commit()

    Logger.info("[load] done", inserted=inserted, updated=updated)
    return inserted, updated


# arq registers functions under ``coroutine.__qualname__``; deriving the names
# here keeps the enqueue side from drifting out of sync with the definitions.
JOB_FUEL_PRICES = fuel_prices_etl.__qualname__
JOB_GAS_STATIONS = gas_stations_import.__qualname__
