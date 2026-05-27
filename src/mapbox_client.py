import httpx

from src.config import settings


class MapboxClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.MAPBOX_API_KEY
        self.directions_endpoint = settings.MAPBOX_DIRECTIONS_ENDPOINT


    async def get_direction_no_instructions(
            self, start: dict, end: dict
    ) -> dict:
        coordinates = f"{start["lng"]},{start["lat"]};{end["lng"]},{end["lat"]}"
        endpoint = self.directions_endpoint + coordinates

        params = {
            "access_token": self.api_key,
            "geometries": "geojson",
        }

        r = await self.client.get(endpoint, params=params)
        r.raise_for_status()

        return r.json()

