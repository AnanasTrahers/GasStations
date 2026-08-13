from datetime import timedelta, datetime

import httpx

from airflow.sdk import task, dag

from src.database import AsyncSessionLocal
from src.prices_module.dal import NetworkDAL, StationDAL
from src.prices_module.schemas import StationRecord
from src.prices_module.scrapers.overpass import OverpassScraper
from src.utils.logs import Logger


@dag(
    schedule="0 4 * * 0",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["stations", "etl", "osm"],
)
def gas_stations_import():

    @task(retries=2, retry_delay=timedelta(minutes=2))
    async def extract_overpass() -> list[dict]:
        """Fetch all branded fuel stations in Ukraine from Overpass API."""
        Logger.info("[extract][overpass] starting")
        async with httpx.AsyncClient() as httpx_client:
            async with OverpassScraper(client=httpx_client) as scraper:
                data = await scraper.collect()
        result = [r.model_dump(mode="json") for r in data]
        Logger.info("[extract][overpass] done", records=len(result))
        return result

    @task
    async def transform(raw_records: list[dict]) -> list[dict]:
        """Deduplicate within the batch (same network + very close coords)."""
        Logger.info("[transform] starting", records=len(raw_records))
        records = [StationRecord(**r) for r in raw_records]

        # Deduplicate: for stations of the same network very close together,
        # keep only the first one (they're the same physical location mapped
        # as multiple OSM nodes).

        # Note: A grid-based approach can theoretically separate points that
        # fall across grid boundaries, but boundary-split duplicates will be
        # caught by the strict 50m proximity constraint in the DAL anyway.
        seen: dict[tuple[str, float, float], StationRecord] = {}
        for rec in records:
            # Round to ~11m grid (4 decimal places ≈ 11m)
            grid_key = (
                rec.network_name,
                round(rec.lat, 4),
                round(rec.lng, 4),
            )
            if grid_key not in seen:
                seen[grid_key] = rec

        deduped = list(seen.values())
        Logger.info(
            "[transform] done",
            before=len(records),
            after=len(deduped),
            removed=len(records) - len(deduped),
        )
        return [r.model_dump(mode="json") for r in deduped]

    @task(retries=1, retry_delay=timedelta(seconds=30))
    async def load(records: list[dict]) -> None:
        """Upsert networks and spatially upsert stations."""
        Logger.info("[load] starting", records=len(records))
        stations = [StationRecord(**r) for r in records]

        async with AsyncSessionLocal() as db_session:
            # Ensure all referenced networks exist.
            network_names = {s.network_name for s in stations}
            network_dal = NetworkDAL(db_session=db_session)
            await network_dal.upsert_bulk_network(data=network_names)
            network_map = await network_dal.get_all_network_map()

            # Spatial upsert stations.
            station_dal = StationDAL(db_session=db_session)
            inserted, updated = await station_dal.spatial_upsert(
                data=stations,
                network_map=network_map,
            )
            await db_session.commit()

        Logger.info(
            "[load] done",
            inserted=inserted,
            updated=updated,
        )

    raw = extract_overpass()
    cleaned = transform(raw)
    load(cleaned)


gas_stations_import()
