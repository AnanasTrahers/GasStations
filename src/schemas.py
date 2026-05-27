from typing import TypedDict, NotRequired


class StationDTO(TypedDict):
    station_id: int
    coordinates: tuple[float, float]
    network_id: int
    network_name: str

    price_per_liter: NotRequired[float]
    fuel_price: NotRequired[float]
    distance: NotRequired[float]
    duration: NotRequired[float]
