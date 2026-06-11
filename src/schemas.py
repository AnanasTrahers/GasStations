from typing import TypedDict, NotRequired
from collections import namedtuple
from dataclasses import dataclass

from src.config import settings

Coords = namedtuple("Coords", ["lng", "lat"])


class StationDTO(TypedDict):
    station_id: int
    coordinates: Coords
    network_id: int
    network_name: str

    price_per_liter: NotRequired[float]
    fuel_price: NotRequired[float]
    distance: NotRequired[float]
    duration: NotRequired[float]


@dataclass
class DirectionsParams:
    geometries: str = "geojson"
    annotations: str = None
    overview: str = None
    steps: str = None
    banner_instructions: str = None
    language: str = None
    voice_instructions: str = None
    voice_units: str = None
    approaches: str = None


    @classmethod
    def setup_full_request(cls):
        return cls(
            annotations="distance,duration,speed",
            overview="full",
            steps="true",
            banner_instructions="true",
            language="uk",
            voice_instructions="true",
            voice_units="metric",
            approaches="curb",
        )
