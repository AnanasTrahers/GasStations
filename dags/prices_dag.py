from datetime import timedelta, datetime

import httpx
from airflow.sdk import task, dag

from src.database import AsyncSessionLocal
from src.prices_module.dal import PricesDAL
from src.prices_module.enums import RegionEnum
from src.prices_module.network_registry import normalize_network_name
from src.prices_module.schemas import FuelPriceRecord
from src.prices_module.scrapers.minfin import MinfinScraper
from src.prices_module.scrapers.vseazs import VseazsScraper
from src.utils.logs import Logger


@dag(
    schedule="0 6 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["prices", "etl", "fuel"],
    params={"region": "KYIV"},
)
def fuel_prices_etl():
    @task
    async def extract_minfin(region: str) -> list[dict]:
        Logger.info("[extract][minfin] starting", region=region)
        async with httpx.AsyncClient() as httpx_client:
            async with MinfinScraper(client=httpx_client) as scraper:
                data = await scraper.collect(region=RegionEnum(region))
        result = [r.model_dump(mode="json") for r in data]
        Logger.info(
            "[extract][minfin] done",
            region=region,
            records=len(result),
        )
        return result

    @task
    async def extract_vseazs(region: str) -> list[dict]:
        Logger.info("[extract][vseazs] starting", region=region)
        async with httpx.AsyncClient() as httpx_client:
            async with VseazsScraper(client=httpx_client) as scraper:
                data = await scraper.collect(region=RegionEnum(region))
        result = [r.model_dump(mode="json") for r in data]
        Logger.info(
            "[extract][vseazs] done",
            region=region,
            records=len(result),
        )
        return result

    @task(
        retries=2,
        retry_delay=timedelta(seconds=30),
        retry_exponential_backoff=True,
    )
    async def transform(
            minfin_records: list[dict], vseazs_records: list[dict]
    ) -> list[dict]:
        Logger.info(
            "[transform] starting",
            minfin=len(minfin_records),
            vseazs=len(vseazs_records),
        )
        all_records = [
            FuelPriceRecord(**r) for r in minfin_records + vseazs_records
        ]
        for record in all_records:
            record.network_name = normalize_network_name(record.network_name)
        result = [r.model_dump(mode="json") for r in all_records]
        Logger.info(
            "[transform] done",
            total=len(result),
        )
        return result

    @task(retries=1, retry_delay=timedelta(seconds=30))
    async def load(records: list[dict]) -> None:
        Logger.info("[load] starting", records=len(records))
        fuel_records = [FuelPriceRecord(**r) for r in records]
        async with AsyncSessionLocal() as db_session:
            prices_dal = PricesDAL(db_session=db_session)
            await prices_dal.insert(fuel_records)
            await db_session.commit()
        Logger.info("[load] done")

    region = "{{ params.region }}"

    minfin_data = extract_minfin(region)
    vseazs_data = extract_vseazs(region)
    merged = transform(minfin_data, vseazs_data)
    load(merged)


fuel_prices_etl()
