from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator
from math import floor

from sqlalchemy.engine.row import Row

from src.utils.logs import Logger


class MatrixDirection(str, Enum):
    FORWARD = "forward"
    BACKWARD = "backward"


class PointCoordinates(BaseModel):
    lng: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class NearbyStationsRequest(BaseModel):
    start: PointCoordinates
    volume: int = Field(..., gt=0)
    fuel_type: str
    fuel_consumption: float = Field(..., gt=0)
    income_per_minute: float = Field(..., ge=0)


class OnRouteStationsRequest(NearbyStationsRequest):
    end: PointCoordinates


class GeoJSONLineString(BaseModel):
    coordinates: list[list[float]]


class SimpleRoute(BaseModel):
    geometry: GeoJSONLineString
    distance: float = Field(..., gt=0)
    duration: float = Field(..., gt=0)


class BaseStation(BaseModel):
    station_id: int
    coordinates: PointCoordinates
    network_id: int
    network_name: str

    price_per_liter: float | None = Field(None, gt=0)
    total_distance_m: float | None = Field(None, gt=0)
    total_duration_s: float | None = Field(None, gt=0)
    fuel_price: float | None = Field(None, gt=0)
    total_price: float | None = Field(None, gt=0)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    def map_row_to_schema(cls, data: Row | dict) -> dict:
        if isinstance(data, dict):
            return data

        res = {
            "station_id": data.station_id,
            "coordinates": {
                "lng": data.lng,
                "lat": data.lat,
            },
            "network_id": data.network_id,
            "network_name": data.network_name
        }

        if hasattr(data, "fraction"):
            res["fraction"] = data.fraction

        return res

    def add_fuel_price_per_liter(self, price_per_liter: float) -> None:
        self.price_per_liter = price_per_liter

    def add_total_distance(self, distance_m: float) -> None:
        self.total_distance_m = distance_m

    def add_total_duration(self, duration_s: float) -> None:
        self.total_duration_s = duration_s

    def calculate_fuel_price(self, volume: float) -> None:
        self.fuel_price = self.price_per_liter * volume


class NearbyStation(BaseStation):

    def calculate_total_price(
            self, fuel_consumption_1km: float, income_per_minute: float
    ) -> None:
        self.total_price = (
                self.fuel_price
                + fuel_consumption_1km * self.total_distance_m / 1000
                + income_per_minute * self.total_duration_s / 60
        )


class OnRouteStation(BaseStation):
    fraction: float = Field(..., ge=0, le=1)

    segment_id: int | None = None
    distance_difference_m: float | None = Field(None, gt=0)
    duration_difference_s: float | None = Field(None, gt=0)

    def assign_segment_id(
            self, route_length_m: float, segment_length_m: float
    ) -> None:
        try:
            self.segment_id = floor(self.fraction * route_length_m / segment_length_m)
        except ZeroDivisionError:
            Logger.error("Division by zero. segment_length_m can't be 0")
            raise

    def calculate_distance_difference(self, original_distance_m: float) -> None:
        self.distance_difference_m = self.total_distance_m - original_distance_m

    def calculate_duration_difference(self, original_duration_s: float) -> None:
        self.duration_difference_s = self.total_duration_s - original_duration_s

    def calculate_total_price(
            self, fuel_consumption_1km: float, income_per_minute: float
    ) -> None:
        self.total_price = (
                self.fuel_price
                + fuel_consumption_1km * self.distance_difference_m / 1000
                + income_per_minute * self.duration_difference_s / 60
        )


class OnRouteStationsResponse(BaseModel):
    original_route: SimpleRoute
    stations: list[OnRouteStation]


class NearbyStationsResponse(BaseModel):
    stations: list[NearbyStation]


class DetailedRoutesRequest(BaseModel):
    start: PointCoordinates
    end: PointCoordinates
    stations_coordinates: list[PointCoordinates] = Field(..., max_length=3)


class BannerText(BaseModel):
    text: str
    type: str | None = None
    modifier: str | None = None


class BannerInstruction(BaseModel):
    distance_along_geometry: float = Field(alias="distanceAlongGeometry")
    primary: BannerText
    sub: BannerText | None = None


class VoiceInstruction(BaseModel):
    distance_along_geometry: float = Field(alias="distanceAlongGeometry")
    announcement: str
    ssml_announcement: str | None = Field(None, alias="ssmlAnnouncement")


class Maneuver(BaseModel):
    location: list[float]
    instruction: str
    type: str
    modifier: str | None = None
    bearing_before: int | None = None
    bearing_after: int | None = None


class RouteStep(BaseModel):
    distance: float = Field(..., gt=0)
    duration: float = Field(..., gt=0)
    geometry: GeoJSONLineString
    maneuver: Maneuver
    banner_instructions: list[BannerInstruction] = Field([], alias="bannerInstructions")
    voice_instructions: list[VoiceInstruction] = Field([], alias="voiceInstructions")

    model_config = ConfigDict(populate_by_name=True)


class RouteAnnotation(BaseModel):
    distance: list[float]
    duration: list[float]
    speed: list[float]


class RouteLeg(BaseModel):
    distance: float = Field(..., gt=0)
    duration: float = Field(..., gt=0)
    steps: list[RouteStep]
    annotation: RouteAnnotation


class DetailedRoute(SimpleRoute):
    legs: list[RouteLeg]


class DetailedRoutesResponse(BaseModel):
    routes: list[DetailedRoute]


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
