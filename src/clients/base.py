import httpx

from src.schemas import MatrixDirection
from src.utils.logs import LoggerMixin


class BaseRoutingClient(LoggerMixin):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @staticmethod
    def _build_coordinates_string(
            coordinates: list[dict]
    ) -> str:
        return ";".join(f"{coord["lng"]},{coord["lat"]}" for coord in coordinates)

    @staticmethod
    def _build_indices_string(coordinates_count: int) -> str:
        return ";".join(str(i) for i in range(1, coordinates_count))

    def _build_matrix_params(
            self,
            coordinates_count: int,
            direction: MatrixDirection,
            additional_params: dict | None = None
    ) -> dict:
        indices_string = self._build_indices_string(coordinates_count)

        params = {
            "annotations": "duration,distance",
            "sources": 0 if direction == MatrixDirection.FORWARD else indices_string,
            "destinations": indices_string if direction == MatrixDirection.FORWARD else 0,
        }

        if additional_params:
            params.update(additional_params)

        return params

    async def _execute_get(self, url: str, params: dict) -> dict:
        self.log_info(f"Executing GET request to {url}")
        try:
            result = await self.client.get(url, params=params)
            result.raise_for_status()
            return result.json()
        except httpx.HTTPStatusError as e:
            self.log_error(f"API rejected request with error status {e.response.status_code}", error=e)
            raise
        except httpx.RequestError as e:
            self.log_error("Network connection failed", error=e)
            raise
        except ValueError as e:
            self.log_error("Failed to decode JSON from response", error=e)
            raise

    async def _call_matrix(
            self,
            endpoint: str,
            anchor: dict,
            coordinates: list[dict],
            direction: MatrixDirection,
            additional_params: dict | None = None
    ) -> dict:
        all_coordinates = [anchor] + coordinates
        coordinates_str = self._build_coordinates_string(all_coordinates)
        url = endpoint + coordinates_str

        params = self._build_matrix_params(len(all_coordinates), direction, additional_params)

        return await self._execute_get(url, params)
