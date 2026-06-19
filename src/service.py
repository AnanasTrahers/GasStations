from collections.abc import Sequence
from datetime import datetime, timezone, timedelta

from shapely import Geometry
from shapely.geometry import LineString
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import select, func, cast
from geoalchemy2 import Geography, WKTElement

from src.config import settings
from src.models import GasStation, FuelPrice, Network
from src.schemas import StationDTO, Coords
from math import floor


def get_route_coordinates(directions_json: dict) -> list[list[float]]:
    return directions_json["routes"][0]["geometry"]["coordinates"]


def get_route_wkt(coordinates_list: list[list[float]]):
    line = LineString(coordinates_list)
    return line.wkt


async def fetch_on_route_stations(
        route_wkt: WKTElement,
        buffer_radius: int,
        session: AsyncSession
) -> Sequence[Row]:
    route_geog = cast(route_wkt, Geography(srid=4326))
    route_geom = cast(route_wkt, Geometry(srid=4326))
    station_geom = cast(GasStation.geog, Geometry(srid=4326))

    stmt = (
        select(
            GasStation.id.label("station_id"),
            GasStation.network_id,
            Network.name.label("network_name"),
            func.ST_X(station_geom).label("lng"),
            func.ST_Y(station_geom).label("lat"),
            func.ST_LineLocatePoint(route_geom, station_geom).label("fraction")
        )
        .select_from(GasStation)
        .join(Network, GasStation.network_id == Network.id)
        .where(func.ST_DWithin(
            route_geog,
            GasStation.geog,
            buffer_radius
        ))
    )
    result = await session.execute(stmt)

    return result.all()


def map_stations_to_dto(rows: Sequence[Row]) -> list[StationDTO]:
    return [
        StationDTO(
            station_id=row.station_id,
            coordinates=Coords(row.lng, row.lat),
            network_id=row.network_id,
            network_name=row.network_name,
            fraction=row.fraction,
        )
        for row in rows
    ]


def assign_segment_ids(
        stations: list[StationDTO],
        route_length_m: float,
        segment_length_m: float
) -> None:
    for station in stations:
        station["segment_id"] = floor(station["fraction"] * route_length_m / segment_length_m)


def get_unique_network_ids(stations: list[StationDTO]) -> set[int]:
    return {station["network_id"] for station in stations}


async def fetch_fuel_prices(
        network_ids: set[int],
        fuel_type: str,
        session: AsyncSession
) -> Sequence[Row]:
    safe_date = (datetime.now(timezone.utc)
                 - timedelta(days=settings.FUEL_PRICE_SAFE_DAYS))

    stmt = (
        select(FuelPrice.network_id, FuelPrice.price)
        .where(
            FuelPrice.fuel_type == fuel_type,
            FuelPrice.network_id.in_(network_ids),
            FuelPrice.created_at >= safe_date
        )
        .distinct(FuelPrice.network_id)
        .order_by(
            FuelPrice.network_id,
            FuelPrice.created_at.desc()
        )
    )

    result = await session.execute(stmt)

    return result.all()


def map_fuel_prices_to_dict(rows: Sequence[Row]) -> dict:
    return {
        row.network_id: row.price for row in rows
    }


def merge_stations_dto_and_prices_dict(
        stations: list[StationDTO],
        fuel_prices: dict
) -> list[StationDTO]:
    filtered_stations = []

    for station in stations:
        fuel_price = fuel_prices.get(station["network_id"])
        if fuel_price is not None:
            station["price_per_liter"] = fuel_price
            filtered_stations.append(station)

    return filtered_stations
