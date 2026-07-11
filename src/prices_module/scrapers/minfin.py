"""Scraper for index.minfin.com.ua fuel price data.

Data source: Consulting Group "A-95" (https://a95.ua/).
Scrapes per-network fuel prices from the /tm/ (trade-mark) page.
"""

import re
from datetime import date, datetime, tzinfo
from decimal import Decimal
from functools import partial
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from src.prices_module.scrapers.base import BaseScraper
from src.prices_module.enums import RegionEnum
from src.prices_module.mappers import MinfinMapper
from src.prices_module.schemas import FuelPriceRecord
from src.prices_module.utils import run_parser
from src.utils.order import get_datetime_kyiv

_UAH_PRICE_RE = re.compile(r"(\d+[.,]\d+)")
_COMMA_TABLE = str.maketrans(",", ".")


class MinfinScraper(BaseScraper):

    SOURCE = "minfin.com.ua"
    BASE_URL = "https://index.minfin.com.ua"
    TM_FUEL = f"{BASE_URL}/ua/markets/fuel/tm/"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client=client)

    @staticmethod
    def _parse_uah(text: str) -> Decimal | None:
        """Extract first UAH price from *text*, returning Decimal or None."""
        text = text.replace("\xa0", "").strip()
        m = _UAH_PRICE_RE.search(text)
        if not m:
            return None
        return Decimal(m[1].translate(_COMMA_TABLE))

    # ── public entry point ────────────────────────────────────────────

    async def collect(
        self,
        *,
        region: RegionEnum,
        date_: datetime | None = None,
    ) -> list[FuelPriceRecord]:
        """Fetch per-network fuel prices for all fuel types."""
        date_ = date_ if date_ else get_datetime_kyiv()
        self.log_info(f"Fetching per-network prices for {region.value}")
        raw = await self._get(self.TM_FUEL)
        return await run_parser(
            partial(self._parse_response, raw.text, date_=date_, region=region)
        )

    # ── internal parser ───────────────────────────────────────────────

    def _parse_response(
        self,
        data: str,
        *,
        date_: datetime,
        region: RegionEnum,
    ) -> list[FuelPriceRecord]:
        """Parse the /tm/ page table (per-network prices)."""
        soup = BeautifulSoup(data, "lxml")
        table = soup.select_one("table.zebra")
        if table is None:
            self.log_warning("Could not find table.zebra on minfin /tm/ page")
            return []

        fuel_columns = self._walk_header(table)

        records: list[FuelPriceRecord] = []
        for row in table.select("tr"):
            cells = row.select("td")
            if len(cells) < 3:
                continue
            link = cells[0].select_one("a")
            network = (
                link.get_text(strip=True) if link
                else cells[0].get_text(strip=True)
            )
            if not network:
                continue

            for col_idx, fuel_type in fuel_columns.items():
                if col_idx >= len(cells):
                    continue
                price = self._parse_uah(cells[col_idx].get_text())
                if price is None:
                    continue
                records.append(
                    FuelPriceRecord(
                        network_name=network,
                        fuel_type=fuel_type,
                        price=price,
                        source=self.SOURCE,
                        created_at=date_,
                        region=region,
                    )
                )

        self.log_info(
            f"Parsed {len(records)} records across "
            f"{len({r.network_name for r in records})} networks"
        )
        return records

    @staticmethod
    def _walk_header(table):
        """Walk <th> elements, respecting colspan, to build column→fuel_type map."""
        result: dict[int, object] = {}
        header_row = table.select_one("tr:has(th)")
        if header_row is None:
            return result
        col = 0
        for th in header_row.select("th"):
            colspan = int(th.get("colspan", 1))
            label = th.get_text(strip=True)
            if label:
                fuel_type = MinfinMapper.parse_fuel_label(label)
                if fuel_type is not None:
                    for offset in range(colspan):
                        result[col + offset] = fuel_type
            col += colspan
        return result


if __name__ == "__main__":
    import asyncio

    async def main():
        async with MinfinScraper() as scraper:
            records = await scraper.collect(region=RegionEnum.KYIV)
            print(f"Records: {len(records)}")
            print(records)

    asyncio.run(main())
