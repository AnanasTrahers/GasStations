import asyncio
from datetime import date
from decimal import Decimal
from functools import partial

import httpx
import re

from bs4 import BeautifulSoup
from src.prices_module.scrapers.base import BaseScraper
from src.prices_module.settings import scraper_settings
from src.prices_module.schemas import FuelPriceRecord
from src.prices_module.enums import FuelTypeEnum, RegionEnum
from src.prices_module.mappers import VseazsMapper
from src.prices_module.utils import run_parser
from src.utils.logs import Logger
from src.utils.order import get_datetime_kyiv


class VseazsScraper(BaseScraper):
    SOURCE = "vseazs"

    MAIN_PAGE = "https://vseazs.com/"
    BASE_URL = "https://vseazs.com/inc/"
    PRICES_TABLE_ENDPOINT = BASE_URL + "get_prices_table.php"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client=client)
        self._cookies_primed = False

    async def _ensure_cookies(self) -> None:
        """Prime the cookie jar by visiting the main page once."""
        if self._cookies_primed:
            return
        await self._get(self.MAIN_PAGE)
        self._cookies_primed = True

    @staticmethod
    def _parse_price(text: str) -> Decimal | None:
        """Parse UAH price from text, filtering out missing/placeholder values."""
        t = text.strip().replace(",", ".").replace("\xa0", "")
        if t in ("-.--", "-", "—", ""):
            return None
        m = re.search(r"(\d+[.,]\d+)", t)
        if not m:
            return None
        return Decimal(m[1])

    def _parse_response(
            self,
            data: str,
            fuel_type: FuelTypeEnum,
            region: RegionEnum,
            date_: date
    ) -> list[FuelPriceRecord]:
        """Parse the HTML table returned by get_prices_table.php.

        The table groups networks by price:
        ``td.PriceTablePriceCell`` holds the price,
        ``td.PriceTableDarkCell`` / ``PriceTableLightCell`` hold network names.
        """
        soup = BeautifulSoup(data, "lxml")
        records: list[FuelPriceRecord] = []
        current_price: Decimal | None = None

        for row in soup.select("tr"):
            price_cell = row.select_one("td.PriceTablePriceCell")
            company_cell = row.select_one(
                "td.PriceTableDarkCell, td.PriceTableLightCell"
            )

            if price_cell is not None:
                current_price = self._parse_price(price_cell.get_text(strip=True))
                continue

            if company_cell is not None and current_price is not None:
                company_name = company_cell.get_text(strip=True)
                if company_name:
                    records.append(
                        FuelPriceRecord(
                            network_name=company_name,
                            fuel_type=fuel_type,
                            price=current_price,
                            source=self.SOURCE,
                            region=region,
                            created_at=date_,
                        )
                    )

        return records

    async def collect(
            self, *,
            region: RegionEnum,
            date_: date | None = None
    ) -> list[FuelPriceRecord]:
        """Fetch per-network fuel prices for all fuel types in parallel."""
        date_ = date_ if date_ else get_datetime_kyiv()
        await self._ensure_cookies()

        region_id = VseazsMapper.get_region(region)

        async def _fetch_one(fuel_type: FuelTypeEnum) -> tuple[str, FuelTypeEnum]:
            fuel_id = VseazsMapper.get_fuel(fuel_type)
            async with scraper_settings.VSEAZS_LIMITER:
                raw: httpx.Response = await self._post(
                    url=self.PRICES_TABLE_ENDPOINT,
                    data={
                        "ID_region": region_id,
                        "ID_fuel": fuel_id,
                        "ID_brand": 89,  # hardcoded to collect all data together
                        "UserDate": date_.strftime("%d.%m.%Y"),
                    },
                    headers={"Referer": self.MAIN_PAGE},
                )
            return raw.text, fuel_type

        raw_results = await asyncio.gather(
            *[_fetch_one(ft) for ft in FuelTypeEnum]
        )
        parse_tasks = [
            run_parser(
                partial(
                    self._parse_response,
                    raw_text,
                    fuel_type=fuel_type,
                    region=region,
                    date_=date_,
                )
            )
            for raw_text, fuel_type in raw_results
        ]
        parsed_chunks = await asyncio.gather(*parse_tasks)
        all_records: list[FuelPriceRecord] = []
        for chunk in parsed_chunks:
            all_records.extend(chunk)
        return all_records


if __name__ == '__main__':
    async def main():
        async with VseazsScraper() as scraper:
            data = await scraper.collect(region=RegionEnum.KYIV)
            print(f"Records: {len(data)}")
            print(data)

    asyncio.run(main())
