import httpx

from src.clients.base import BaseRoutingClient
from src.config import settings
from src.schemas import MatrixDirection


class OSRMClient(BaseRoutingClient):
    def __init__(self, client: httpx.AsyncClient):
        super().__init__(client)
        self.table_endpoint = settings.OSRM_TABLE_ENDPOINT

    async def get_table(
            self,
            anchor: dict,
            coordinates: list[dict],
            direction: MatrixDirection
    ) -> dict:
        return await self._call_matrix(
            endpoint=self.table_endpoint,
            anchor=anchor,
            coordinates=coordinates,
            direction=direction
        )
