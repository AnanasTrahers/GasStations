import uuid
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.models import FuelPrice, GasStation, Network
from src.prices_module.schemas import FuelPriceRecord, StationRecord
from src.utils.logs import LoggerMixin


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
                    **d.model_dump(exclude={"network_name", "created_at"}, mode="json")
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


class StationDAL(BaseDAL):
    _model = GasStation

    _PROXIMITY_M = 50
    # Two stations of the same network within this distance (meters)
    # are considered the same physical location.

    async def spatial_upsert(
            self,
            data: list[StationRecord],
            network_map: dict[str, UUID],
    ) -> tuple[int, int]:
        """Insert new stations or update geometry of existing ones.
        Returns ``(inserted, updated)`` counts.
        """
        valid_records = []
        for rec in data:
            nid = network_map.get(rec.network_name)
            if nid is not None:
                valid_records.append({
                    "id": uuid.uuid4(),
                    "network_id": nid,
                    "lng": rec.lng,
                    "lat": rec.lat,
                })

        if not valid_records:
            return 0, 0

        # Create temporary table for incoming batch
        await self.db_session.execute(text(
            "CREATE TEMP TABLE IF NOT EXISTS tmp_new_stations ("
            "    id UUID,"
            "    network_id UUID,"
            "    geog GEOGRAPHY(Point, 4326)"
            ") ON COMMIT DROP"
        ))
        await self.db_session.execute(text("TRUNCATE tmp_new_stations"))

        # Bulk insert into temp table
        await self.db_session.execute(
            text("INSERT INTO tmp_new_stations (id, network_id, geog) "
                 "VALUES (:id, :network_id, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))"),
            valid_records
        )

        # Update existing stations
        update_sql = text(f"""
            WITH matched AS (
                SELECT DISTINCT ON (g.id)
                    g.id as existing_id,
                    t.geog as new_geog
                FROM gas_stations g
                JOIN tmp_new_stations t ON g.network_id = t.network_id
                WHERE ST_DWithin(g.geog, t.geog, {self._PROXIMITY_M})
            )
            UPDATE gas_stations
            SET geog = matched.new_geog
            FROM matched
            WHERE gas_stations.id = matched.existing_id
        """)
        result = await self.db_session.execute(update_sql)
        updated = result.rowcount

        # Insert new stations
        insert_sql = text(f"""
            INSERT INTO gas_stations (id, network_id, geog)
            SELECT t.id, t.network_id, t.geog
            FROM tmp_new_stations t
            WHERE NOT EXISTS (
                SELECT 1
                FROM gas_stations g
                WHERE g.network_id = t.network_id
                AND ST_DWithin(g.geog, t.geog, {self._PROXIMITY_M})
            )
        """)
        result = await self.db_session.execute(insert_sql)
        inserted = result.rowcount

        return inserted, updated
