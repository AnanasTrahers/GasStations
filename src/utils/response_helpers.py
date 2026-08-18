from src.utils.logs import Logger


def get_route_coordinates(directions_json: dict) -> list[list[float]]:
    try:
        return directions_json["routes"][0]["geometry"]["coordinates"]
    except (KeyError, IndexError, TypeError) as e:
        Logger.error("Failed to get route coordinates from Directions JSON", error=e)
        raise


def get_route_length(directions_json: dict) -> float:
    try:
        return directions_json["routes"][0]["distance"]
    except (KeyError, IndexError, TypeError) as e:
        Logger.error("Failed to get route length from Directions JSON", error=e)
        raise


def get_route_duration(directions_json: dict) -> float:
    try:
        return directions_json["routes"][0]["duration"]
    except (KeyError, IndexError, TypeError) as e:
        Logger.error("Failed to get route duration from Directions JSON", error=e)
        raise


def get_matrix_distances(matrix_json: dict) -> list[list[float]]:
    try:
        return matrix_json["distances"]
    except (KeyError, IndexError, TypeError) as e:
        Logger.error("Failed to get list of distances from Matrix JSON", error=e)
        raise


def get_matrix_durations(matrix_json: dict) -> list[float] | list[list[float]]:
    try:
        return matrix_json["durations"]
    except (KeyError, IndexError, TypeError) as e:
        Logger.error("Failed to get list of durations from Matrix JSON", error=e)
        raise


def get_polygon(isochrones_json: dict) -> list[list[list[float]]]:
    try:
        return isochrones_json["features"][0]["geometry"]["coordinates"]
    except (KeyError, IndexError, TypeError) as e:
        Logger.error("Failed to get polygon from Isochrones JSON", error=e)
        raise
