from dataclasses import asdict

import httpx

from src.clients.base import BaseRoutingHTTPXClient
from src.config import settings
from src.schemas import DirectionsParams, MatrixDirection


class MapboxHTTPXClient(BaseRoutingHTTPXClient):
    directions_endpoint = "https://api.mapbox.com/directions/v5/mapbox/driving-traffic/"
    matrix_endpoint = "https://api.mapbox.com/directions-matrix/v1/mapbox/driving-traffic/"
    isochrone_endpoint = "https://api.mapbox.com/isochrone/v1/mapbox/driving-traffic/"

    def __init__(self, client: httpx.AsyncClient):
        super().__init__(client)
        self.api_key = settings.MAPBOX_API_KEY

    @staticmethod
    def _build_approaches_string(n: int) -> str:
        approaches = ["unrestricted"]
        approaches += ["curb"] * (n - 1)

        return ";".join(approaches)

    async def get_direction(
            self, coords: list[dict], params: DirectionsParams
    ) -> dict:
        coordinates = self._build_coordinates_string(coords)
        endpoint = self.directions_endpoint + coordinates

        params = {key: value for key, value in asdict(params).items() if value is not None}

        params["access_token"] = self.api_key
        params["approaches"] = self._build_approaches_string(len(coords))

        return await self._execute_get(endpoint, params)

    async def get_forward_matrix(
            self,
            start: dict,
            coordinates: list[dict]
    ) -> dict:
        return await self._call_matrix(
            endpoint=self.matrix_endpoint,
            anchor=start,
            coordinates=coordinates,
            direction=MatrixDirection.FORWARD,
            additional_params={"access_token": self.api_key}
        )

    async def get_isochrone(self, point: dict) -> dict:
        coordinates_str = self._build_coordinates_string([point])
        endpoint = self.isochrone_endpoint + coordinates_str

        params = {
            "access_token": self.api_key,
            "contours_minutes": settings.ISOCHRONE_CONTOURS_MINUTES,
            "polygons": "true",
            "generalize": 50,
        }

        return await self._execute_get(endpoint, params)
