from collections.abc import Sequence

from shapely.geometry import LineString
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import select, func, cast
from geoalchemy2 import Geography
from geoalchemy2.shape import to_shape

from src.models import GasStation
from src.schemas import StationDTO


async def get_coordinates(directions_json: dict) -> list[list[float]]:
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
        point = to_shape(station.geom)

        result.append(
            StationDTO(
                station_id=station.id,
                coordinates=f"{point.x},{point.y}",
                network_id=station.network_id,
                network_name=station.network.name
            )
        )

    return result
