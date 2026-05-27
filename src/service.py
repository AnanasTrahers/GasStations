from collections.abc import Sequence

from shapely.geometry import LineString
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import select, func, cast
from geoalchemy2 import Geography

from src.models import GasStation


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
    )
    result = await session.execute(stmt)

    return result.scalars().all()
