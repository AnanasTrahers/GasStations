from pathlib import Path

from shapely import wkb
from shapely.geometry import Point, LineString
from shapely.geometry.base import BaseGeometry

from src.utils.logs import LoggerMixin

class GeoValidator(LoggerMixin):
    def __init__(self):
        self._ukraine_polygon: BaseGeometry
        
        try:
            base_dir = Path(__file__).resolve().parent.parent
            wkb_path = base_dir / "assets" / "ukraine_buffered.wkb"
            
            with open(wkb_path, "rb") as f:
                self._ukraine_polygon = wkb.load(f)
            
            self.log_info("Successfully loaded optimized Ukraine WKB polygon for validation.")
        except Exception as e:
            self.log_error("Failed to load optimized Ukraine WKB polygon. Halting startup.", error=e)
            raise RuntimeError(f"Critical asset missing: {wkb_path}. Cannot start application.") from e

    def contains_point(self, point: Point) -> bool:
        return self._ukraine_polygon.contains(point)

    def contains_line(self, line: LineString) -> bool:
        return self._ukraine_polygon.contains(line)

geo_validator = GeoValidator()

def is_point_in_ukraine(lat: float, lng: float) -> bool:
    """Check if a specific point is within Ukraine."""
    try:
        return geo_validator.contains_point(Point(lng, lat))
    except Exception as e:
        geo_validator.log_error(f"Failed to validate point [{lat}, {lng}]", error=e)
        return False

def is_route_in_ukraine(coordinates: list[list[float]]) -> bool:
    """
    Check if an entire route (list of [lng, lat]) is within Ukraine.
    The pre-computed WKB is already buffered by ~2km.
    """
    if not coordinates or len(coordinates) < 2:
        return True
        
    try:
        return geo_validator.contains_line(LineString(coordinates))
    except Exception as e:
        geo_validator.log_error("Failed to parse route coordinates for validation", error=e)
        return False
