from typing import TypedDict, NotRequired
from collections import namedtuple
from dataclasses import dataclass


Coords = namedtuple("Coords", ["lng", "lat"])


class StationDTO(TypedDict):
    station_id: int
    coordinates: Coords
    network_id: int
    network_name: str
    fraction: float

    segment_id: NotRequired[int]
    price_per_liter: NotRequired[float]
    total_distance_m: NotRequired[float]
    total_duration_s: NotRequired[float]
    distance_difference_m: NotRequired[float]
    duration_difference_s: NotRequired[float]
    fuel_price: NotRequired[float]


@dataclass
class DirectionsParams:
    geometries: str = "geojson"
    overview: str = "full"
    annotations: str = None
    steps: str = None
    banner_instructions: str = None
    language: str = None
    voice_instructions: str = None
    voice_units: str = None


    @classmethod
    def setup_full_request(cls):
        return cls(
            annotations="distance,duration,speed",
            steps="true",
            banner_instructions="true",
            language="uk",
            voice_instructions="true",
            voice_units="metric"
        )
