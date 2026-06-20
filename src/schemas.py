from enum import Enum
from collections import namedtuple
from dataclasses import dataclass
from pydantic import BaseModel, ConfigDict
from math import floor


Coords = namedtuple("Coords", ["lng", "lat"])

class MatrixDirection(str, Enum):
    FORWARD = "forward"
    BACKWARD = "backward"


class Station(BaseModel):
    station_id: int
    lng: float
    lat: float
    network_id: int
    network_name: str
    fraction: float

    segment_id: int | None = None
    price_per_liter: float | None = None
    total_distance_m: float | None = None
    total_duration_s: float | None = None
    distance_difference_m: float | None = None
    duration_difference_s: float | None = None
    fuel_price: float | None = None
    total_price: float | None = None

    model_config = ConfigDict(from_attributes=True)

    def assign_segment_id(
            self,
            route_length_m: float,
            segment_length_m: float
    ) -> None:
        self.segment_id = floor(self.fraction * route_length_m / segment_length_m)

    def add_fuel_price_per_liter(self, price_per_liter: float) -> None:
        self.price_per_liter = price_per_liter

    def add_total_distance(self, distance_m: float) -> None:
        self.total_distance_m = distance_m

    def add_total_duration(self, duration_s: float) -> None:
        self.total_duration_s = duration_s

    def calculate_distance_difference(self, original_distance_m: float) -> None:
        self.distance_difference_m = self.total_distance_m - original_distance_m

    def calculate_duration_difference(self, original_duration_s: float) -> None:
        self.duration_difference_s = self.total_duration_s - original_duration_s

    def calculate_fuel_price(self, volume: float) -> None:
        self.fuel_price = self.price_per_liter * volume

    def calculate_total_price(
            self, fuel_consumption_1km: float, income_per_minute: float
    ) -> None:
        self.total_price = (
            self.fuel_price
            + fuel_consumption_1km * self.distance_difference_m / 1000
            + income_per_minute * self.duration_difference_s / 60
        )


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
