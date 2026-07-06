from itertools import groupby, islice
from typing import TypeVar

from sqlalchemy.engine.row import Row, Sequence

from src.clients.mapbox import MapboxClient
from src.clients.osrm import OsrmClient
from src.repositories import DBRepository
from src.schemas import (
    OnRouteStation, NearbyStation, BaseStation, MatrixDirection,
    PointCoordinates, SimpleRoute, GeoJSONLineString, DirectionsParams
)
from src.utils.logs import Logger
from src.utils.response_helpers import (
    get_matrix_distances, get_matrix_durations,
    get_route_coordinates, get_route_length, get_route_duration, get_polygon
)
from src.utils.wkt_builders import get_polygon_wkt

StationType = TypeVar('StationType', bound=BaseStation)


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


async def fetch_and_merge_fuel_prices(
        stations: list[StationType],
        fuel_type: str,
        db_repo: DBRepository
):
    unique_networks_ids = get_unique_network_ids(stations)
    fuel_prices = await db_repo.prices.fetch_for_networks(unique_networks_ids, fuel_type)

    fuel_prices_dict = map_fuel_prices_to_dict(fuel_prices)

    return merge_stations_and_prices(stations, fuel_prices_dict)


async def get_and_apply_matrices(
        stations: list[StationType],
        osrm: OsrmClient,
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


async def fetch_and_build_simple_route(
        mapbox: MapboxClient,
        start: PointCoordinates,
        end: PointCoordinates
) -> SimpleRoute:
    Logger.info("Fetching route from Mapbox and building SimpleRoute...")
    response = await mapbox.get_direction(
        [start.model_dump(), end.model_dump()], DirectionsParams()
    )

    return SimpleRoute(
        geometry=GeoJSONLineString(
            coordinates=get_route_coordinates(response)
        ),
        distance=get_route_length(response),
        duration=get_route_duration(response)
    )


async def fetch_and_build_polygon_wkt(
        mapbox: MapboxClient,
        start: PointCoordinates
) -> str:
    Logger.info("Fetching isochrone from Mapbox and building polygon WKT...")
    response = await mapbox.get_isochrone(start.model_dump())
    polygon = get_polygon(response)
    return get_polygon_wkt(polygon)
