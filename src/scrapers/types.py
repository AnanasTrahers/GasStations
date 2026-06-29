"""Shared types for fuel price scrapers."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class FuelPriceRecord(BaseModel):
    """Single fuel price data point from any source.

    All scrapers normalise their output into this shape so downstream
    consumers (CLI, DB writers) work with a single type.
    """

    network_name: str
    """Display name of the gas station network (e.g. 'OKKO', 'WOG')."""

    fuel_type: str
    """Fuel variant label (e.g. 'A-95', 'diesel', 'LPG')."""

    price: Decimal | None
    """Price in UAH per litre."""

    source: str
    """Identifier of the scraper that produced this record."""

    date: date
    """Date when the price was observed / reported by the source."""

    region: Optional[str] = None
    """Optional region name if the source provides regional breakdowns."""


class ScrapingResult(BaseModel):
    """Container returned by every scraper, holding records + metadata."""

    records: list[FuelPriceRecord] = field(default_factory=list)
    source: str = ""
    scraped_at: date = field(default_factory=date.today)
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return len(self.records) > 0
