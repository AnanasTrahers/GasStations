from dataclasses import asdict

import httpx

from src.config import settings
from src.schemas import Coords, DirectionsParams


class MapboxClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.MAPBOX_API_KEY
        self.directions_endpoint = settings.MAPBOX_DIRECTIONS_ENDPOINT
        self.matrix_endpoint = settings.MAPBOX_MATRIX_ENDPOINT
        self.isochrone_endpoint = settings.MAPBOX_ISOCHRONE_ENDPOINT

    @staticmethod
    def _build_coordinates_string(
            coordinates: list[Coords]
    ) -> str:
        return ";".join(f"{coord.lng},{coord.lat}" for coord in coordinates)

    @staticmethod
    def _get_destination_or_source_indices(coordinates: str) -> str:
        count = coordinates.count(";")

        return ";".join(str(i) for i in range(1, count + 1))

    @staticmethod
    def _build_approaches_string(n: int) -> str:
        approaches = ["unrestricted"]
        approaches += ["curb"] * (n - 1)

        return ";".join(approaches)

    async def get_direction(
            self, coords: list[Coords], params: DirectionsParams
    ) -> dict:
        coordinates = self._build_coordinates_string(coords)
        endpoint = self.directions_endpoint + coordinates

        params = {key: value for key, value in asdict(params).items() if value is not None}

        params["access_token"] = self.api_key
        params["approaches"] = self._build_approaches_string(len(coords))

        r = await self.client.get(endpoint, params=params)
        r.raise_for_status()

        return r.json()

    async def get_forward_matrix(
            self,
            start: Coords,
            coordinates: list[Coords]
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
            end: Coords,
            coordinates: list[Coords]
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

    async def get_isochrones(self, point: Coords, radiuses: list[int]) -> dict:
        coordinates_str = self._build_coordinates_string([point])
        endpoint = self.isochrone_endpoint + coordinates_str

        params = {
            "access_token": self.api_key,
            "contours_minutes": ",".join(radiuses),
            "polygons": "true",
            "generalize": 50,
        }

        r = await self.client.get(endpoint, params=params)
        r.raise_for_status()

        return r.json()
