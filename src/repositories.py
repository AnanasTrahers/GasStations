from datetime import datetime, timezone, timedelta

from geoalchemy2 import Geography, WKTElement, Geometry
from sqlalchemy.engine.row import Row, Sequence
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import select, func, cast

from src.config import business_settings
from src.models import GasStation, FuelPrice, Network, User, Subscription, SubscriptionHistory
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

    async def get_by_purchase_token(self, purchase_token: str) -> Subscription | None:
        stmt = select(Subscription).where(Subscription.purchase_token == purchase_token)
        self.log_info("Fetching subscription by purchase token...")
        try:
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            self.log_error("DB query failed while fetching subscription by purchase token")
            raise

    async def create_or_update(
        self,
        user_id: str,
        *,
        purchase_token: str,
        product_id: str,
        platform: str,
        starts_at: datetime | None,
        expires_at: datetime | None,
        status: str,
        is_premium: bool,
    ) -> Subscription:
        self.log_info(f"Upserting subscription for user {user_id}")
        try:
            stmt = select(Subscription).where(Subscription.user_id == user_id)
            result = await self.session.execute(stmt)
            sub = result.scalar_one_or_none()

            if sub is None:
                sub = Subscription(user_id=user_id)
                self.session.add(sub)

            sub.purchase_token = purchase_token
            sub.product_id = product_id
            sub.platform = platform
            sub.starts_at = starts_at
            sub.expires_at = expires_at
            sub.status = status
            sub.is_premium = is_premium
            sub.updated_at = datetime.now(timezone.utc)

            await self.session.flush()
            return sub
        except SQLAlchemyError:
            self.log_error("DB query failed while upserting subscription")
            raise

    async def update(self, subscription: Subscription) -> None:
        self.log_info(f"Updating subscription for user {subscription.user_id}")
        try:
            subscription.updated_at = datetime.now(timezone.utc)
            self.session.add(subscription)
            await self.session.flush()
        except SQLAlchemyError:
            self.log_error("DB query failed while updating subscription")
            raise

    async def log_history(
        self,
        user_id: str,
        event_type: str,
        *,
        platform: str | None = None,
        purchase_token: str | None = None,
        product_id: str | None = None,
        raw_payload: dict | None = None,
    ) -> None:
        self.log_info(f"Logging subscription history for user {user_id}: {event_type}")
        try:
            record = SubscriptionHistory(
                user_id=user_id,
                event_type=event_type,
                platform=platform,
                purchase_token=purchase_token,
                product_id=product_id,
                event_time=datetime.now(timezone.utc),
                raw_payload=raw_payload,
            )
            self.session.add(record)
            await self.session.flush()
        except SQLAlchemyError:
            self.log_error("DB query failed while logging subscription history")
            raise

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class DBRepository:
    def __init__(self, session: AsyncSession):
        self.stations = StationsRepository(session)
        self.prices = PricesRepository(session)
        self.users = UsersRepository(session)
        self.subscriptions = SubscriptionsRepository(session)

