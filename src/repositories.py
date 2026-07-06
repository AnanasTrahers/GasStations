from datetime import datetime, timezone, timedelta

from geoalchemy2 import Geography, WKTElement
from shapely import Geometry
from sqlalchemy.engine.row import Row, Sequence
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import select, func, cast

from src.config import settings
from src.models import GasStation, FuelPrice, Network
from src.utils.logs import Logger


class StationsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def fetch_on_route(
            self,
            route_wkt: WKTElement,
            buffer_radius: int
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
            result = await self.session.execute(stmt)
            return result.all()
        except SQLAlchemyError:
            Logger.error("DB query failed while fetching on-route stations")
            raise

    async def fetch_nearby(
            self,
            polygon_wkt: WKTElement
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
            result = await self.session.execute(stmt)
            return result.all()
        except SQLAlchemyError:
            Logger.error("DB query failed while fetching nearby stations")
            raise


class PricesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def fetch_for_networks(
            self,
            network_ids: set[int],
            fuel_type: str
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
            result = await self.session.execute(stmt)
            return result.all()
        except SQLAlchemyError:
            Logger.error("DB query failed while fetching fuel prices")
            raise


class DBRepository:
    def __init__(self, session: AsyncSession):
        self.stations = StationsRepository(session)
        self.prices = PricesRepository(session)
