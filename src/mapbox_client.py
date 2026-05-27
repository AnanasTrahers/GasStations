import httpx

from src.config import settings


class MapboxClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.MAPBOX_API_KEY
        self.directions_endpoint = settings.MAPBOX_DIRECTIONS_ENDPOINT
        self.matrix_endpoint = settings.MAPBOX_MATRIX_ENDPOINT

    @staticmethod
    def _build_coordinates_string(
            coordinates: list[tuple[float, float]]
    ) -> str:
        return ";".join(f"{lng},{lat}" for lng, lat in coordinates)

    @staticmethod
    def _get_destination_or_source_indices(coordinates: str) -> str:
        count = coordinates.count(";")

        return ";".join(str(i) for i in range(1, count + 1))

    async def get_direction_no_instructions(
            self, start: tuple[float, float], end: tuple[float, float]
    ) -> dict:
        coordinates = self._build_coordinates_string([start, end])
        endpoint = self.directions_endpoint + coordinates

        params = {
            "access_token": self.api_key,
            "geometries": "geojson",
        }

        r = await self.client.get(endpoint, params=params)
        r.raise_for_status()

        return r.json()

    async def get_forward_matrix(
            self,
            start: tuple[float, float],
            coordinates: list[tuple[float, float]]
    ) -> dict:
        coordinates_str = self._build_coordinates_string([start] + coordinates)
        endpoint = self.matrix_endpoint + coordinates_str

        destination_indices = self._get_destination_or_source_indices(coordinates_str)

        params = {
            "access_token": self.api_key,
            "annotations": "duration,distance",
            "sources": 0,
            "destinations": destination_indices,
        }

        r = await self.client.get(endpoint, params=params)
        r.raise_for_status()

        return r.json()

    async def get_backward_matrix(
            self,
            end: tuple[float, float],
            coordinates: list[tuple[float, float]]
    ) -> dict:
        coordinates_str = self._build_coordinates_string([end] + coordinates)
        endpoint = self.matrix_endpoint + coordinates_str

        source_indices = self._get_destination_or_source_indices(coordinates_str)

        params = {
            "access_token": self.api_key,
            "annotations": "duration,distance",
            "sources": source_indices,
            "destinations": 0
        }

        r = await self.client.get(endpoint, params=params)
        r.raise_for_status()

        return r.json()
