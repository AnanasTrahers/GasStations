from collections.abc import Sequence
from datetime import datetime, timezone, timedelta
from itertools import groupby, islice

from shapely import Geometry
from shapely.geometry import LineString
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import select, func, cast
from geoalchemy2 import Geography, WKTElement

from src.config import settings
from src.models import GasStation, FuelPrice, Network
from src.schemas import Station


def get_route_coordinates(directions_json: dict) -> list[list[float]]:
    return directions_json["routes"][0]["geometry"]["coordinates"]


def get_route_wkt(coordinates_list: list[list[float]]):
    line = LineString(coordinates_list)
    return WKTElement(line.wkt, srid=4326)


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


def assign_segment_ids(
        stations: list[Station],
        route_length_m: float,
        segment_length_m: float
) -> None:
    for station in stations:
        station.assign_segment_id(route_length_m, segment_length_m)


def get_unique_network_ids(stations: list[Station]) -> set[int]:
    return {station.network_id for station in stations}


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


def merge_stations_and_prices(
        stations: list[Station],
        fuel_prices: dict
) -> list[Station]:
    filtered_stations = []

    for station in stations:
        fuel_price = fuel_prices.get(station.network_id)
        if fuel_price is not None:
            station.add_fuel_price_per_liter(fuel_price)
            filtered_stations.append(station)

    return filtered_stations


def merge_matrixes(
        forward_matrix: list[float],
        backward_matrix: list[list[float]]
) -> list[float]:
    merged_list = []

    for i in range(len(forward_matrix)):
        merged_list.append(forward_matrix[i] + backward_matrix[i][0])

    return merged_list


def add_total_distances_and_durations(
        stations: list[Station], distances_m: list, durations_s: list
) -> None:
    for station, distance, duration in zip(stations, distances_m, durations_s):
        station.add_total_distance(distance)
        station.add_total_duration(duration)


def calculate_stations_metrics(
        stations: list[Station],
        original_distance_m: float,
        original_duration_s: float,
        volume: float,
        fuel_consumption_1km: float,
        income_per_minute: float,
) -> None:
    for station in stations:
        station.calculate_distance_difference(original_distance_m)
        station.calculate_duration_difference(original_duration_s)
        station.calculate_fuel_price(volume)
        station.calculate_total_distance(fuel_consumption_1km, income_per_minute)


def get_top_stations_for_segment(
        stations: list[Station],
        max_per_network: int
) -> list[Station]:
    top_stations = []
    stations.sort(key=lambda x: (x.network_id, x.segment_id, x.total_price))

    for key, group in groupby(stations, key=lambda x: (x.network_id, x.segment_id)):
        top_stations.extend(islice(group, max_per_network))

    return sorted(top_stations, key=lambda x: x["total_price"])
