from collections.abc import Sequence
from datetime import datetime, timezone, timedelta
from itertools import groupby, islice
from typing import TypeVar

from shapely import Geometry
from shapely.geometry import LineString
from shapely.geometry.polygon import Polygon
from sqlalchemy.engine.row import Row
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import select, func, cast
from geoalchemy2 import Geography, WKTElement

from src.clients.osrm import OSRMClient
from src.config import settings
from src.models import GasStation, FuelPrice, Network
from src.schemas import OnRouteStation, NearbyStation, BaseStation, MatrixDirection
from src.utils.logs import Logger

StationType = TypeVar('StationType', bound=BaseStation)


def get_route_coordinates(directions_json: dict) -> list[list[float]]:
    try:
        return directions_json["routes"][0]["geometry"]["coordinates"]
    except (KeyError, IndexError, TypeError):
        Logger.error("Failed to get route coordinates from Directions JSON")
        raise


def get_route_length(directions_json: dict) -> float:
    try:
        return directions_json["routes"][0]["distance"]
    except (KeyError, IndexError, TypeError):
        Logger.error("Failed to get route length from Directions JSON")
        raise


def get_route_duration(directions_json: dict) -> float:
    try:
        return directions_json["routes"][0]["duration"]
    except (KeyError, IndexError, TypeError):
        Logger.error("Failed to get route duration from Directions JSON")
        raise


def get_matrix_distances(matrix_json: dict) -> list[list[float]]:
    try:
        return matrix_json["distances"]
    except (KeyError, IndexError, TypeError):
        Logger.error("Failed to get list of distances from Matrix JSON")
        raise


def get_matrix_durations(matrix_json: dict) -> list[float] | list[list[float]]:
    try:
        return matrix_json["durations"]
    except (KeyError, IndexError, TypeError):
        Logger.error("Failed to get list of durations from Matrix JSON")
        raise


def get_polygon(isochrones_json: dict) -> list[list[float]]:
    try:
        return isochrones_json["features"][0]["geometry"]["coordinates"]
    except (KeyError, IndexError, TypeError):
        Logger.error("Failed to get polygon from Isochrones JSON")
        raise


def get_route_wkt(coordinates_list: list[list[float]]) -> WKTElement:
    try:
        return WKTElement(LineString(coordinates_list).wkt, srid=4326)
    except ValueError:
        Logger.error("Failed to create LineString")
        raise


def get_polygon_wkt(coordinates_list: list[list[float]]) -> WKTElement:
    try:
        return WKTElement(Polygon(coordinates_list).wkt, srid=4326)
    except ValueError:
        Logger.error("Failed to create Polygon")
        raise


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
    Logger.info("Fetching on-route stations...")
    try:
        result = await session.execute(stmt)
        return result.all()
    except SQLAlchemyError:
        Logger.error("DB query failed while fetching on-route stations")
        raise


def assign_segment_ids(
        stations: list[OnRouteStation],
        route_length_m: float,
        segment_length_m: float
) -> None:
    Logger.info("Assigning segment ids...")
    for station in stations:
        station.assign_segment_id(route_length_m, segment_length_m)
    Logger.info(f"Assigned segment ids to {len(stations)} stations")


def get_unique_network_ids(stations: list[StationType]) -> set[int]:
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

    Logger.info("Fetching fuel prices...")
    try:
        result = await session.execute(stmt)
        return result.all()
    except SQLAlchemyError:
        Logger.error("DB query failed while fetching fuel prices")
        raise


def map_fuel_prices_to_dict(rows: Sequence[Row]) -> dict:
    return {
        row.network_id: row.price for row in rows
    }


def merge_stations_and_prices(
        stations: list[StationType],
        fuel_prices: dict
) -> list[StationType]:
    filtered_stations = []

    Logger.info("Merging stations and fuel prices...")
    for station in stations:
        fuel_price = fuel_prices.get(station.network_id)
        if fuel_price is not None:
            station.add_fuel_price_per_liter(fuel_price)
            filtered_stations.append(station)

    Logger.info(f"Merged. Kept {len(filtered_stations)} stations out of {len(stations)}")
    return filtered_stations


def get_stations_coordinates_dicts(stations: list[StationType]) -> list[dict]:
    return [
        station.coordinates.model_dump() for station in stations
    ]


def merge_matrices(
        forward_matrix: list[list[float]],
        backward_matrix: list[list[float]]
) -> list[float]:
    merged_list = []

    Logger.info("Merging forward and backward matrices...")
    try:
        for i in range(len(backward_matrix)):
            merged_list.append(forward_matrix[0][i] + backward_matrix[i][0])
        return merged_list
    except IndexError:
        Logger.error("Mismatched list length: matrices don't align")
        raise


def add_total_distances_and_durations(
        stations: list[StationType], distances_m: list, durations_s: list
) -> None:
    Logger.info("Adding total distances and durations to stations...")
    try:
        for station, distance, duration in zip(stations, distances_m, durations_s, strict=True):
            station.add_total_distance(distance)
            station.add_total_duration(duration)
    except ValueError:
        Logger.error("Mismatched list length: stations, distances and durations don't align")
        raise


def calculate_on_route_stations_metrics(
        stations: list[OnRouteStation],
        original_distance_m: float,
        original_duration_s: float,
        volume: float,
        fuel_consumption_1km: float,
        income_per_minute: float,
) -> None:
    Logger.info(
        "Calculating distance and duration differences, and fuel prices for on-route stations..."
    )
    for station in stations:
        station.calculate_distance_difference(original_distance_m)
        station.calculate_duration_difference(original_duration_s)
        station.calculate_fuel_price(volume)
        station.calculate_total_price(fuel_consumption_1km, income_per_minute)


def calculate_nearby_stations_metrics(
        stations: list[NearbyStation],
        volume: float,
        fuel_consumption_1km: float,
        income_per_minute: float,
) -> None:
    Logger.info("Calculating fuel prices for nearby stations...")
    for station in stations:
        station.calculate_fuel_price(volume)
        station.calculate_total_price(fuel_consumption_1km, income_per_minute)


def get_top_on_route_stations(
        stations: list[OnRouteStation],
        max_per_network: int
) -> list[OnRouteStation]:
    top_stations = []
    stations.sort(key=lambda x: (x.network_id, x.segment_id, x.total_price))

    Logger.info(
        f"Filtering top {max_per_network} on-route stations for each network for each segment..."
    )
    for key, group in groupby(stations, key=lambda x: (x.network_id, x.segment_id)):
        top_stations.extend(islice(group, max_per_network))

    Logger.info(f"Filtered. Kept {len(top_stations)} stations out of {len(stations)}")
    return sorted(top_stations, key=lambda x: x.total_price)


def get_top_nearby_stations(
        stations: list[NearbyStation],
        max_per_network: int
) -> list[NearbyStation]:
    top_stations = []
    stations.sort(key=lambda x: (x.network_id, x.total_price))

    Logger.info(
        f"Filtering top {max_per_network} nearby stations..."
    )
    for key, group in groupby(stations, key=lambda x: x.network_id):
        top_stations.extend(islice(group, max_per_network))

    Logger.info(f"Filtered. Kept {len(top_stations)} stations out of {len(stations)}")
    return sorted(top_stations, key=lambda x: x.total_price)


async def fetch_nearby_stations(
        polygon_wkt: WKTElement,
        session: AsyncSession
) -> Sequence[Row]:
    polygon_geog = cast(polygon_wkt, Geography(srid=4326))
    station_geom = cast(GasStation.geog, Geometry(srid=4326))

    stmt = (
        select(
            GasStation.id.label("station_id"),
            GasStation.network_id,
            Network.name.label("network_name"),
            func.ST_X(station_geom).label("lng"),
            func.ST_Y(station_geom).label("lat")
        )
        .select_from(GasStation)
        .join(Network, GasStation.network_id == Network.id)
        .where(func.ST_Intersects(GasStation.geog, polygon_geog))
    )

    Logger.info("Fetching nearby stations...")
    try:
        result = await session.execute(stmt)
        return result.all()
    except SQLAlchemyError:
        Logger.error("DB query failed while fetching nearby stations")
        raise


async def fetch_and_merge_fuel_prices(
        stations: list[StationType],
        fuel_type: str,
        session: AsyncSession
):
    unique_networks_ids = get_unique_network_ids(stations)
    fuel_prices = await fetch_fuel_prices(unique_networks_ids, fuel_type, session)

    fuel_prices_dict = map_fuel_prices_to_dict(fuel_prices)

    return merge_stations_and_prices(stations, fuel_prices_dict)


async def get_and_apply_matrices(
        stations: list[StationType],
        osrm: OSRMClient,
        start: dict,
        end: dict,
) -> None:
    stations_coordinates = get_stations_coordinates_dicts(stations)
    forward_matrix = await osrm.get_table(
        start, stations_coordinates, MatrixDirection.FORWARD
    )
    forward_distances = get_matrix_distances(forward_matrix)
    forward_durations = get_matrix_durations(forward_matrix)

    backward_matrix = await osrm.get_table(
        end, stations_coordinates, MatrixDirection.BACKWARD
    )
    backward_distances = get_matrix_distances(backward_matrix)
    backward_durations = get_matrix_durations(backward_matrix)

    distances_list = merge_matrices(forward_distances, backward_distances)
    durations_list = merge_matrices(forward_durations, backward_durations)

    add_total_distances_and_durations(stations, distances_list, durations_list)
