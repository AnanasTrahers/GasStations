from collections.abc import Sequence
from datetime import datetime, timezone, timedelta

from shapely.geometry import LineString, Point
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import select, func, cast
from geoalchemy2 import Geography
from geoalchemy2.shape import to_shape

from src.config import settings
from src.models import GasStation, FuelPrice
from src.schemas import StationDTO


def get_coordinates(directions_json: dict) -> list[list[float]]:
    return directions_json["routes"][0]["geometry"]["coordinates"]


async def fetch_on_route_stations(
        coordinates: list[list[float]],
        buffer_radius: int,
        session: AsyncSession
) -> Sequence[GasStation]:
    line = LineString(coordinates)

    stmt = (
        select(GasStation)
        .where(func.ST_DWithin(
            cast(line.wkt, Geography),
            GasStation.geom,
            buffer_radius
        ))
        .options(joinedload(GasStation.network, innerjoin=True))
    )
    result = await session.execute(stmt)

    return result.scalars().all()


def map_stations_to_dto(
        gas_stations: Sequence[GasStation]
) -> list[StationDTO]:
    result = []
    for station in gas_stations:
        point = cast(Point, to_shape(station.geom))

        result.append(
            StationDTO(
                station_id=station.id,
                coordinates=(point.x, point.y),
                network_id=station.network_id,
                network_name=station.network.name
            )
        )

    return result


async def fetch_fuel_prices_per_liter(
        gas_stations: list[StationDTO],
        fuel_type: str,
        session: AsyncSession
) -> dict[int, float]:
    network_ids = {station["network_id"] for station in gas_stations}
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

    return {row.network_id: row.price for row in result.all()}


def filter_gas_stations(
        gas_stations: list[StationDTO],
        prices_map: dict[int, float],
) -> list[StationDTO]:
    filtered_stations = []

    for station in gas_stations:
        fuel_price = prices_map.get(station["network_id"])
        if fuel_price is not None:
            station["price_per_liter"] = fuel_price
            filtered_stations.append(station)

    return filtered_stations


def calculate_fuel_prices(
        gas_stations: list[StationDTO],
        volume: int
) -> list[StationDTO]:
    for station in gas_stations:
        station["fuel_price"] = station["price_per_liter"] * volume

    return gas_stations


def calculate_distances_and_durations(
        gas_stations: list[StationDTO],
        forward_matrix: dict,
        backward_matrix: dict
) -> list[StationDTO]:
    forward_distances = forward_matrix["distances"]
    backward_distances = backward_matrix["distances"]

    forward_durations = forward_matrix["durations"]
    backward_durations = backward_matrix["durations"]

    new_stations = []

    for i, station in enumerate(gas_stations):
        f_distance = forward_distances[0][i]
        b_distance = backward_distances[i][0]

        if f_distance is None or b_distance is None:
            continue
        station["distance"] = f_distance + b_distance

        f_duration = forward_durations[0][i]
        b_duration = backward_durations[i][0]

        if f_duration is None or b_duration is None:
            continue
        station["duration"] = f_duration + b_duration

        new_stations.append(station)

    return new_stations
