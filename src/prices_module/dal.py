from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.models import FuelPrice, Network
from src.prices_module.schemas import FuelPriceRecord
from src.utils.logs import LoggerMixin
from sqlalchemy.ext.asyncio.session import AsyncSession


class BaseDAL(LoggerMixin):
    _model = None

    def __init__(self, db_session: AsyncSession = None):
        self.db_session = db_session


class NetworkDAL(BaseDAL):
    _model = Network

    async def upsert_bulk_network(self, data: set[str]):
        stmt = insert(self._model).values(
            [{"name": name} for name in data]
        ).on_conflict_do_nothing(index_elements=["name"])
        await self.db_session.execute(stmt)

    async def get_all_network_map(self):
        stmt = select(self._model)
        results = await self.db_session.scalars(stmt)
        return {r.name: r.id for r in results}


class PricesDAL(BaseDAL):
    _model = FuelPrice

    async def insert(self, data: list[FuelPriceRecord]):
        network_names = set(d.network_name for d in data)
        network_dal = NetworkDAL(self.db_session)
        await network_dal.upsert_bulk_network(data=network_names)
        network_map = await network_dal.get_all_network_map()

        stmt = insert(self._model).values(
            [
                {
                    "network_id": network_map[d.network_name],
                    "created_at": d.created_at.date(),
                    **d.model_dump(exclude=("network_name", "created_at"), mode="json")
                }
                for d in data
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["source", "fuel_type", "network_id", "created_at"],
            # where=(self._model.__table__.c.created_at != stmt.excluded.created_at),
            set_=dict(price=stmt.excluded.price)
        )
        await self.db_session.execute(stmt)
