"""Shared types for fuel price scrapers."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from src.prices_module.enums import FuelTypeEnum, RegionEnum


class FuelPriceRecord(BaseModel):
    """Single fuel price data point from any source.

    All scrapers normalise their output into this shape so downstream
    consumers (CLI, DB writers) work with a single type.
    """

    network_name: str
    """Display name of the gas station network (e.g. 'OKKO', 'WOG')."""

    fuel_type: FuelTypeEnum
    """Fuel variant label (e.g. 'A-95', 'diesel', 'LPG')."""

    price: Decimal | None
    """Price in UAH per litre."""

    source: str
    """Identifier of the scraper that produced this record."""

    created_at: datetime
    """Date when the price was observed / reported by the source."""

    region: RegionEnum | None = None
    """Optional region name if the source provides regional breakdowns."""


class StationRecord(BaseModel):
    """Single gas station data point from the Overpass/OSM source.

    The station-import DAG normalises Overpass output into this shape
    before upserting into ``gas_stations``.
    """

    network_name: str
    """Canonical display name of the gas station network."""

    lat: float
    """WGS-84 latitude."""

    lng: float
    """WGS-84 longitude."""

    osm_id: int
    """Original OSM node/way ID (for dedup reference)."""
