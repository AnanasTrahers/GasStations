"""Scraper for vseazs.com fuel price data.

vseazs.com provides two data surfaces:
1. Static HTML price bars (8 fuel types) rendered server-side on the
   main page — always present, gives current selection (region + brand).
2. AJAX endpoints that return structured HTML when called with form data:
   - ``POST /inc/get_prices_table.php`` → per-network prices for a given
     region + fuel-type + brand combination.
   - ``POST /get_prices_brand.php`` → 8 price values (delimited string)
     for a given region + brand.

We use both: price bars for a quick summary and the AJAX table endpoint
to get per-network breakdowns.

Known numeric IDs (discovered from page source):
- Regions: Kyiv = 9
- Price modes: max = 87, min = 88, avg = 89
- Brand: OKKO = 12, WOG = 9, SOCAR = 100, Shell = 24, UPG = 102,
  KLO = 30, Ukrnafta = 6, AMIC = 166, BVS = 186, MANGO = 107,
  Marshal = 138, Авантаж 7 = 56, БРСМ-нафта = 61, Маркет = 23
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date
from decimal import Decimal
from typing import Optional

from bs4 import BeautifulSoup, Tag

from src.scrapers.base import BaseScraper, ScrapingError
from src.scrapers.types import FuelPriceRecord, ScrapingResult

logger = logging.getLogger(__name__)

# ――― Constants ―――――――――――――――――――――――――――――――――――――――――――――――

_BASE = "https://vseazs.com"
_MAIN_PAGE = _BASE + "/"
_PRICE_TABLE_ENDPOINT = f"{_BASE}/inc/get_prices_table.php"
_PRICE_BRAND_ENDPOINT = f"{_BASE}/get_prices_brand.php"

# Delimiter used by get_prices_brand.php response.
# The JS code splits on '-#-#-#-#-#-#-#-#' but actual server responses
# use '#' as the field separator.  We handle both.
_PRICE_DELIM = "-#-#-#-#-#-#-#-#"
_PRICE_DELIM_FALLBACK = "#"

# Order of fuel types in the 8-element price array (positions 1–8),
# matching PriceID1 … PriceID8 in the page DOM.
_FUEL_TYPE_ORDER: list[str] = [
    "",           # index 0 — header / metadata
    "a98",        # PriceID1 → A-98
    "a95_plus",   # PriceID2 → A-95+
    "a95",        # PriceID3 → A-95
    "a92",        # PriceID4 → A-92
    "a80",        # PriceID5 → A-80
    "diesel",     # PriceID6 → ДП
    "diesel_plus",# PriceID7 → ДП+
    "lpg",        # PriceID8 → Газ
]

# ――― Region / brand numeric IDs ――――――――――――――――――――――――――――――――

REGION_KYIV = 9
PRICE_AVG = 89
PRICE_MAX = 87
PRICE_MIN = 88

# Brand IDs that correspond to major Ukrainian networks.
_KNOWN_BRANDS: dict[int, str] = {
    12: "ОККО",
    9: "WOG",
    100: "SOCAR",
    24: "Shell",
    102: "UPG",
    30: "КЛО",
    6: "Укрнафта",
    166: "AMIC",
    186: "BVS",
    107: "MANGO",
    138: "Marshal",
    56: "Авантаж 7",
    61: "БРСМ-нафта",
    23: "Маркет",
}

# ――― Helpers ――――――――――――――――――――――――――――――――――――――――――――――――

_DASH_RE = re.compile(r"^[-–—]+$")
_UAH_PRICE_RE = re.compile(r"(\d+[.,]\d+)")


def _is_missing_price(text: str) -> bool:
    """Return True if *text* represents "no price"."""
    t = text.strip().replace("\xa0", "")
    return t in ("-.--", "-", "—", "") or bool(_DASH_RE.match(t))


def _parse_price(text: str) -> Optional[Decimal]:
    """Parse UAH price from text, filtering out missing/placeholder values."""
    if _is_missing_price(text):
        return None
    t = text.strip().replace(",", ".").replace("\xa0", "")
    m = _UAH_PRICE_RE.search(t)
    if not m:
        return None
    return Decimal(m[1])


def _fuel_label_to_key(label: str) -> str:
    """Map display label like 'A-95' or 'ДП' to internal key."""
    mapping = {
        "a-98": "a98",
        "a-95+": "a95_plus",
        "a-95": "a95",
        "a-92": "a92",
        "a-80": "a80",
        "дп": "diesel",
        "дп+": "diesel_plus",
        "газ": "lpg",
    }
    return mapping.get(label.strip().lower(), label.strip().lower())


# ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――
#  Public scraper
# ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――――


class VseazsScraper(BaseScraper):
    """Scrape fuel prices from vseazs.com.

    Three strategies (all async):

    1. ``scrape()`` — parse static price bars from main page. Fast,
       returns avg prices for default region/brand.

    2. ``scrape_networks()`` — for each known brand, POST to the
       price-table AJAX endpoint. Returns per-network prices for a
       single fuel type.

    3. ``scrape_brand_prices()`` — POST to the brand-prices AJAX
       endpoint for every brand. Returns all 8 fuel types per brand.

    Usage::

        async with VseazsScraper() as scraper:
            summary = await scraper.scrape()
            per_network = await scraper.scrape_networks(fuel_type="a95")
    """

    source = "vseazs.com"
    base_url = _BASE

    # ―― Per-instance state (populated lazily) ―――――――――――――――――――

    _cookies_primed: bool = False

    # ── top-level entry points ──────────────────────────────────────

    async def _do_scrape(self, *, target_date: date) -> ScrapingResult:
        """Default: parse static price bars from main page."""
        return await self._scrape_price_bars()

    async def scrape_networks(
        self,
        *,
        fuel_type: str = "a95",
        region_id: int = REGION_KYIV,
        brand_id: int = PRICE_AVG,
    ) -> ScrapingResult:
        """Fetch per-network prices for one fuel type via AJAX table.

        Args:
            fuel_type: One of the fuel keys ('a95', 'diesel', 'lpg', …).
            region_id: Numeric region ID (9 = Kyiv).
            brand_id: 89 = avg, 87 = max, 88 = min, or a specific brand ID.
        """
        fuel_id = self._fuel_type_to_id(fuel_type)
        today = date.today()
        await self._ensure_cookies()

        date_str = today.strftime("%d.%m.%Y")
        logger.info(
            "vseazs table: region=%d fuel=%s(%d) brand=%d",
            region_id,
            fuel_type,
            fuel_id,
            brand_id,
        )
        resp = await self._post(
            _PRICE_TABLE_ENDPOINT,
            data={
                "ID_region": str(region_id),
                "ID_fuel": str(fuel_id),
                "ID_brand": str(brand_id),
                "UserDate": date_str,
            },
            headers={"Referer": _MAIN_PAGE},
        )

        return self._parse_price_table(resp.text, fuel_type=fuel_type)

    async def scrape_brand_prices(
        self,
        *,
        region_id: int = REGION_KYIV,
        brand_id: int = PRICE_AVG,
    ) -> ScrapingResult:
        """Get all 8 fuel-type prices for one brand via AJAX.

        Returns a result where each record has the same network_name
        (the resolved brand) and one of the 8 fuel types.
        """
        today = date.today()
        await self._ensure_cookies()

        brand_name = _KNOWN_BRANDS.get(brand_id, str(brand_id))
        logger.info(
            "vseazs brand prices: region=%d brand=%s(%d)",
            region_id,
            brand_name,
            brand_id,
        )
        # vseazs expects Ukrainian date format: DD.MM.YYYY
        date_str = today.strftime("%d.%m.%Y")
        resp = await self._post(
            _PRICE_BRAND_ENDPOINT,
            data={
                "ID_region": str(region_id),
                "ID_brand": str(brand_id),
                "UserDate": date_str,
            },
            headers={"Referer": _MAIN_PAGE},
        )

        return self._parse_brand_response(resp.content, brand_name)

    async def scrape_all_brands(
        self,
        *,
        region_id: int = REGION_KYIV,
        brand_ids: Optional[list[int]] = None,
    ) -> ScrapingResult:
        """Convenience: iterate over all known brands, merge results."""
        ids = brand_ids or list(_KNOWN_BRANDS)
        all_records: list[FuelPriceRecord] = []
        all_errors: list[str] = []

        for bid in ids:
            sub = await self.scrape_brand_prices(
                region_id=region_id, brand_id=bid
            )
            all_records.extend(sub.records)
            all_errors.extend(sub.errors)

        return ScrapingResult(records=all_records, errors=all_errors)

    # ── internal: parse static page ─────────────────────────────────

    async def _scrape_price_bars(self) -> ScrapingResult:
        resp = await self._get(_MAIN_PAGE)
        soup = BeautifulSoup(resp.text, "lxml")
        records: list[FuelPriceRecord] = []
        today = date.today()
        errors: list[str] = []

        # Also grab the currently selected brand name from the dropdown.
        brand_title_el = soup.select_one("#stella_azs_title2")
        brand_name = (
            brand_title_el.get_text(strip=True)
            if brand_title_el
            else "Average price"
        )

        for idx in range(1, 9):  # price_bar_1 … price_bar_8
            price_el = soup.select_one(f"#PriceID{idx}")
            title_el = soup.select_one(f"#price_title_{idx}")
            if price_el is None or title_el is None:
                errors.append(f"Missing price bar #{idx}")
                continue

            fuel_label = title_el.get_text(strip=True)
            fuel_key = _fuel_label_to_key(fuel_label)
            price_val = price_el.get_text(strip=True)
            price = _parse_price(price_val)

            if price is None:
                continue  # unavailable fuel type, skip

            records.append(
                FuelPriceRecord(
                    network_name=brand_name,
                    fuel_type=fuel_key,
                    price=price,
                    source=self.source,
                    scraped_at=today,
                )
            )

        logger.info("vseazs price bars: %d fuel types", len(records))
        return ScrapingResult(records=records, errors=errors)

    # ── internal: parse AJAX responses ──────────────────────────────

    def _parse_price_table(
        self, html: str, *, fuel_type: str = "a95"
    ) -> ScrapingResult:
        """Parse the HTML table returned by get_prices_table.php.

        The table groups networks by price value:
        ``<td class="PriceTablePriceCell">`` holds the price,
        ``<td class="PriceTableDarkCell">`` or ``PriceTableLightCell``
        holds the network name(s).
        """
        soup = BeautifulSoup(html, "lxml")
        records: list[FuelPriceRecord] = []
        today = date.today()

        rows = soup.select("tr")
        current_price: Optional[Decimal] = None

        for row in rows:
            price_cell = row.select_one("td.PriceTablePriceCell")
            company_cell = row.select_one(
                "td.PriceTableDarkCell, td.PriceTableLightCell"
            )

            if price_cell is not None:
                text = price_cell.get_text(strip=True)
                current_price = _parse_price(text)
                continue

            if company_cell is not None and current_price is not None:
                company_name = company_cell.get_text(strip=True)
                if company_name:
                    records.append(
                        FuelPriceRecord(
                            network_name=company_name,
                            fuel_type=fuel_type,
                            price=current_price,
                            source=self.source,
                            scraped_at=today,
                        )
                    )
                continue

        return ScrapingResult(records=records)

    def _parse_brand_response(
        self, raw: bytes, brand_name: str
    ) -> ScrapingResult:
        """Parse the delimited response from get_prices_brand.php.

        The server responds with ``windows-1251``-encoded text.
        Actual format observed::

            <BOM>\\n<header>#price1#price2#...#price8#\\r\\n

        where *header* is a metadata value (``52.00`` for avg, empty
        for per-brand) and prices use ``-`` as placeholder for N/A.

        The JS function ``ReloadPrices`` maps p[1]…p[8] (0-based after
        splitting on the long delimiter) to PriceID1…PriceID8.
        """
        today = date.today()
        try:
            text = raw.decode("windows-1251")
        except (UnicodeDecodeError, LookupError):
            text = raw.decode("utf-8", errors="replace")

        # Try the JS-advertised delimiter first, then fall back to '#'.
        delim = (_PRICE_DELIM if _PRICE_DELIM in text
                 else _PRICE_DELIM_FALLBACK)
        parts = text.split(delim)

        records: list[FuelPriceRecord] = []

        # After splitting, index 0 is the BOM + header line.
        # Indices 1–8 (if present) correspond to fuel types 1–8.
        max_idx = min(len(parts), len(_FUEL_TYPE_ORDER))
        for idx in range(1, max_idx):
            price_raw = parts[idx].strip()
            if not price_raw:
                continue
            # Strip trailing \\r\\n that may stick to the last element.
            price_raw = price_raw.rstrip("\r\n")
            price = _parse_price(price_raw)
            if price is None:
                continue
            records.append(
                FuelPriceRecord(
                    network_name=brand_name,
                    fuel_type=_FUEL_TYPE_ORDER[idx],
                    price=price,
                    source=self.source,
                    scraped_at=today,
                )
            )

        return ScrapingResult(records=records)

    # ── helpers ─────────────────────────────────────────────────────

    async def _ensure_cookies(self) -> None:
        """Prime the cookie jar by visiting the main page once."""
        if self._cookies_primed:
            return
        await self._get(_MAIN_PAGE)
        self._cookies_primed = True

    @staticmethod
    def _fuel_type_to_id(fuel_type: str) -> int:
        """Map internal fuel key to the numeric ID used by vseazs."""
        mapping = {
            "a98": 1,
            "a95_plus": 2,
            "a95": 3,
            "a92": 4,
            "a80": 5,
            "diesel": 6,
            "diesel_plus": 7,
            "lpg": 8,
        }
        return mapping.get(fuel_type, 3)


if __name__ == '__main__':
    async def main():
        async with VseazsScraper() as scraper:
            res = await scraper.scrape_all_brands()
            with open("vseazs_t1.json", "w") as f:
                f.write(res.model_dump_json())
            res = await scraper.scrape_networks()
            with open("vseazs_t2.json", "w") as f:
                f.write(res.model_dump_json())
            res = await scraper.scrape()
            with open("vseazs_t3.json", "w") as f:
                f.write(res.model_dump_json())

    asyncio.run(main())