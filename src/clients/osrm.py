import httpx

from src.clients.base import BaseRoutingHTTPXClient
from src.schemas import MatrixDirection


class OSRMHTTPXClient(BaseRoutingHTTPXClient):
    table_endpoint = "http://osrm_engine:5000/table/v1/driving/"

    def __init__(self, client: httpx.AsyncClient):
        super().__init__(client)

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
