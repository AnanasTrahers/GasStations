from datetime import datetime, timezone, timedelta

from geoalchemy2 import Geography, WKTElement, Geometry
from sqlalchemy.engine.row import Row, Sequence
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import select, func, cast

from src.config import business_settings
from src.models import GasStation, FuelPrice, Network, User, Subscription
from src.utils.logs import LoggerMixin


class StationsRepository(LoggerMixin):
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
        self.log_info("Fetching on-route stations...")
        try:
            result = await self.session.execute(stmt)
            return result.all()
        except SQLAlchemyError:
            self.log_error("DB query failed while fetching on-route stations")
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

        self.log_info("Fetching nearby stations...")
        try:
            result = await self.session.execute(stmt)
            return result.all()
        except SQLAlchemyError:
            self.log_error("DB query failed while fetching nearby stations")
            raise


class PricesRepository(LoggerMixin):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def fetch_unique_fuel_types(self) -> Sequence[str]:
        safe_date = (datetime.now(timezone.utc)
                     - timedelta(days=business_settings.FUEL_PRICE_SAFE_DAYS))

        stmt = (
            select(FuelPrice.fuel_type)
            .where(
                FuelPrice.fuel_type.is_not(None),
                FuelPrice.created_at >= safe_date
            )
            .distinct()
        )

        self.log_info("Fetching unique fuel types...")
        try:
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except SQLAlchemyError:
            self.log_error("DB query failed while fetching unique fuel types")
            raise

    async def fetch_for_networks(
            self,
            network_ids: set[int],
            fuel_type: str
    ) -> Sequence[Row]:
        safe_date = (datetime.now(timezone.utc)
                     - timedelta(days=business_settings.FUEL_PRICE_SAFE_DAYS))

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

        self.log_info("Fetching fuel prices...")
        try:
            result = await self.session.execute(stmt)
            return result.all()
        except SQLAlchemyError:
            self.log_error("DB query failed while fetching fuel prices")
            raise


class UsersRepository(LoggerMixin):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_google_id(self, google_id: str) -> User | None:
        stmt = select(User).where(User.google_id == google_id)
        self.log_info("Fetching user by Google ID...")
        try:
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            self.log_error("DB query failed while fetching user")
            raise

    async def create(self, google_id: str, email: str) -> User:
        self.log_info("Creating user with default subscription...")
        try:
            user = User(google_id=google_id, email=email)
            self.session.add(user)
            await self.session.flush()

            subscription = Subscription(user_id=user.id)
            self.session.add(subscription)

            await self.session.commit()
            return user
        except SQLAlchemyError:
            self.log_error("DB query failed while creating user")
            await self.session.rollback()
            raise


class SubscriptionsRepository(LoggerMixin):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: str) -> Subscription | None:
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        self.log_info("Fetching subscription by user ID...")
        try:
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            self.log_error("DB query failed while fetching subscription")
            raise


class DBRepository:
    def __init__(self, session: AsyncSession):
        self.stations = StationsRepository(session)
        self.prices = PricesRepository(session)
        self.users = UsersRepository(session)
        self.subscriptions = SubscriptionsRepository(session)
