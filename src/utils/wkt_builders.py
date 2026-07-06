from geoalchemy2 import WKTElement
from shapely.geometry import LineString
from shapely.geometry.polygon import Polygon

from src.utils.logs import Logger


def get_route_wkt(coordinates_list: list[list[float]]) -> WKTElement:
    try:
        return WKTElement(LineString(coordinates_list).wkt, srid=4326)
    except ValueError:
        Logger.error("Failed to create LineString")
        raise


def get_polygon_wkt(coordinates_list: list[list[float]]) -> WKTElement:
    try:
        return WKTElement(Polygon(coordinates_list).wkt, srid=4326)
    except ValueError:
        Logger.error("Failed to create Polygon")
        raise
