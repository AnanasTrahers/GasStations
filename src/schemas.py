from typing import TypedDict, NotRequired
from collections import namedtuple


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
