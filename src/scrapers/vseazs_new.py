import asyncio
from datetime import date
from decimal import Decimal

import httpx
import re

from bs4 import BeautifulSoup
from src.scrapers import BaseScraper, FuelPriceRecord
from src.scrapers.enums import FuelTypeEnum, RegionEnum
from src.scrapers.mappers import VseazsMapper
from src.utils.logs import LoggerMixin


class VseazsScraper(BaseScraper, LoggerMixin):

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
                            date=date_,
                        )
                    )

        return records

    async def collect(
            self, *,
            fuel_type: FuelTypeEnum,
            region: RegionEnum,
            date_: date | None = None
    ) -> list[FuelPriceRecord]:
        date_ = date_ if date_ else date.today()
        await self._ensure_cookies()
        raw: httpx.Response = await self._retry(
            method="POST",
            url=self.PRICES_TABLE_ENDPOINT,
            data={
                "ID_region": VseazsMapper.get_region(region),
                "ID_fuel": VseazsMapper.get_fuel(fuel_type),
                "ID_brand": 89,  # hardcoded to collect all data together
                "UserDate": date_.strftime("%d.%m.%Y"),
            },
            headers={"Referer": self.MAIN_PAGE},
        )
        parsed = self._parse_response(
            data=raw.text,
            fuel_type=fuel_type,
            region=region,
            date_=date_
        )
        return parsed


if __name__ == '__main__':
    async def main():
        async with VseazsScraper() as scraper:
            data = await scraper.collect(
                fuel_type=FuelTypeEnum.A95,
                region=RegionEnum.KYIV,
            )
            print(data)


    asyncio.run(main())
