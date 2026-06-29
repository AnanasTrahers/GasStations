"""Scraper for index.minfin.com.ua fuel price pages.

Data source: Consulting Group "A-95" (https://a95.ua/).

Pages scraped:
- Main fuel page → national average prices (static HTML table).
- /tm/ (trade-mark) → per-network prices.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal
from typing import Optional

from bs4 import BeautifulSoup, Tag

from src.scrapers.base import BaseScraper, ScrapingError
from src.scrapers.types import FuelPriceRecord, ScrapingResult

logger = logging.getLogger(__name__)

# ――― URL templates (language-prefixed, Ukrainian) ―――――――――――――――――――

_BASE = "https://index.minfin.com.ua"
_MAIN_FUEL = f"{_BASE}/ua/markets/fuel/"
_TM_FUEL = f"{_BASE}/ua/markets/fuel/tm/"

# ――― Fuel-type label mapping ――――――――――――――――――――――――――――――――――――
# Minfin uses long Ukrainian names; we normalise to short keys.

_FUEL_LABEL_MAP: list[tuple[str, str]] = [
    # Order matters: more specific patterns first.
    ("а-95 преміум", "a95_premium"),
    ("а 95 преміум", "a95_premium"),
    ("а 95+", "a95_premium"),
    ("а-95+", "a95_premium"),
    ("а 95", "a95"),
    ("а-95", "a95"),
    ("а 92", "a92"),
    ("а-92", "a92"),
    ("дизельне паливо", "diesel"),
    ("дизель", "diesel"),
    ("дп", "diesel"),
    ("газ автомобільний", "lpg"),
    ("газ", "lpg"),
]

_UAH_PRICE_RE = re.compile(r"(\d+[.,]\d+)")

# Prices on this site use comma as decimal separator.
_COMMA_TABLE = str.maketrans(",", ".")


def _parse_uah(text: str) -> Optional[Decimal]:
    """Extract first UAH price from *text*, returning Decimal or None."""
    text = text.replace("\xa0", "").strip()
    m = _UAH_PRICE_RE.search(text)
    if not m:
        return None
    return Decimal(m[1].translate(_COMMA_TABLE))


def _normalise_fuel(label: str) -> str:
    """Map a Ukrainian fuel label to a short internal key."""
    # Collapse whitespace, replace non-breaking space, lowercase.
    key = (
        label.strip()
        .replace("\xa0", " ")
        .replace("\n", " ")
        .lower()
    )
    # Collapse multiple spaces.
    while "  " in key:
        key = key.replace("  ", " ")

    for pattern, short in _FUEL_LABEL_MAP:
        if pattern in key:
            return short
    return key


# ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――
#  Public scraper
# ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――――


class MinfinScraper(BaseScraper):
    """Scrape fuel prices from index.minfin.com.ua.

    Two scraping modes:
    - *national* (the main fuel page) — five fuel types, national averages.
    - *networks* (the /tm/ sub-page) — per-network breakdown.

    Usage::

        async with MinfinScraper() as scraper:
            result = await scraper.scrape()          # national
            result = await scraper.scrape_networks()  # per-network
    """

    source = "minfin.com.ua"
    base_url = _BASE

    # ── top-level entry points ──────────────────────────────────────

    async def _do_scrape(self, *, target_date: date) -> ScrapingResult:
        """Default scrape → national averages from the main fuel page."""
        return await self._scrape_main_page()

    async def scrape_networks(self) -> ScrapingResult:
        """Return per-network prices from the /tm/ page."""
        return await self._scrape_tm_page()

    # ── main page: national averages ────────────────────────────────

    async def _scrape_main_page(self) -> ScrapingResult:
        logger.info("Fetching minfin main fuel page")
        resp = await self._get(_MAIN_FUEL)
        soup = BeautifulSoup(resp.text, "lxml")

        table = soup.select_one("table.line")
        if table is None:
            raise ScrapingError(
                "Could not find <table class='line'> on minfin fuel page"
            )

        records: list[FuelPriceRecord] = []
        today = date.today()

        for row in table.select("tr"):
            cells = row.select("td")
            if len(cells) < 3:
                continue
            fuel_label = cells[0].get_text(strip=True)
            fuel_key = _normalise_fuel(fuel_label)
            price = _parse_uah(cells[2].get_text())
            if price is None:
                continue
            records.append(
                FuelPriceRecord(
                    network_name="",
                    fuel_type=fuel_key,
                    price=price,
                    source=self.source,
                    scraped_at=today,
                    region="Україна",
                )
            )

        logger.info("Minfin national: %d fuel types", len(records))
        return ScrapingResult(records=records)

    # ── trade-mark page: per-network ────────────────────────────────

    async def _scrape_tm_page(self) -> ScrapingResult:
        logger.info("Fetching minfin /tm/ page")
        resp = await self._get(_TM_FUEL)
        soup = BeautifulSoup(resp.text, "lxml")

        # The /tm/ page uses <table class='zebra'>.
        table = soup.select_one("table.zebra")
        if table is None:
            raise ScrapingError(
                "Could not find table.zebra on minfin /tm/ page"
            )

        # Column layout: col 0+1 (colspan) = network name,
        # cols 2+ = fuel prices.  Header row has <th> with fuel labels.
        fuel_columns: dict[int, str] = {}

        def _walk_header_th(table: Tag) -> dict[int, str]:
            """Walk <th> elements, respecting colspan to get real column index."""
            result: dict[int, str] = {}
            header_row = table.select_one("tr:has(th)")
            if header_row is None:
                return result
            col = 0
            for th in header_row.select("th"):
                colspan = int(th.get("colspan", 1))
                label = th.get_text(strip=True)
                if label:
                    normalised = _normalise_fuel(label)
                    if normalised != label:
                        # For each column this th spans, use the same fuel type.
                        # (colspan on fuel headers is unusual but handle it.)
                        for offset in range(colspan):
                            result[col + offset] = normalised
                col += colspan
            return result

        fuel_columns = _walk_header_th(table)

        records: list[FuelPriceRecord] = []
        today = date.today()

        for row in table.select("tr"):
            cells = row.select("td")
            if len(cells) < 3:
                continue
            # Network name is inside an <a> tag in the first cell.
            link = cells[0].select_one("a")
            network = (
                link.get_text(strip=True) if link
                else cells[0].get_text(strip=True)
            )
            if not network:
                continue

            for idx, fuel_type in fuel_columns.items():
                if idx >= len(cells):
                    continue
                price = _parse_uah(cells[idx].get_text())
                if price is None:
                    continue
                records.append(
                    FuelPriceRecord(
                        network_name=network,
                        fuel_type=fuel_type,
                        price=price,
                        source=self.source,
                        scraped_at=today,
                    )
                )

        logger.info(
            "Minfin /tm/: %d records across %d networks",
            len(records),
            len({r.network_name for r in records}),
        )
        return ScrapingResult(records=records)
