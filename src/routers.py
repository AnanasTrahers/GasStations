import asyncio

from fastapi import APIRouter, status, Depends
from httpx import AsyncClient
from sqlalchemy.ext.asyncio.session import AsyncSession
from pydantic import TypeAdapter

from src.clients.mapbox import MapboxClient
from src.clients.osrm import OSRMClient
from src.config import settings
from src.database import get_db
from src.dependencies import get_mapbox_client, get_osrm_client
from src.schemas import (
    OnRouteStationsResponse,
    OnRouteStationsRequest,
    DirectionsParams,
    Station,
    MatrixDirection,
    SimpleRoute,
    GeoJSONLineString,
    DetailedRoutesResponse, DetailedRoutesRequest, DetailedRoute
)
from src.service import (
    get_route_coordinates,
    get_route_wkt,
    fetch_on_route_stations,
    assign_segment_ids,
    get_route_length,
    get_unique_network_ids,
    fetch_fuel_prices,
    map_fuel_prices_to_dict,
    merge_stations_and_prices,
    get_stations_coordinates_dicts,
    get_matrix_distances,
    get_matrix_durations,
    merge_matrixes,
    add_total_distances_and_durations,
    calculate_stations_metrics,
    get_route_duration,
    get_top_stations_for_segment
)

router = APIRouter(prefix="/v1/optimization", tags=["Stations"])


@router.post(
    "/on-route",
    response_model=OnRouteStationsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_on_route_stations(
        data: OnRouteStationsRequest,
        session: AsyncSession = Depends(get_db),
        mapbox_client: AsyncClient = Depends(get_mapbox_client),
        osrm_client: AsyncClient = Depends(get_osrm_client)
):
    mapbox = MapboxClient(mapbox_client)
    directions_params = DirectionsParams()
    directions_response = await mapbox.get_direction(
        [data.start.model_dump(), data.end.model_dump()], directions_params
    )

    original_route_coordinates = get_route_coordinates(directions_response)
    original_route_wkt = get_route_wkt(original_route_coordinates)
    stations_rows = await fetch_on_route_stations(
        original_route_wkt, settings.BUFFER_RADIUS_M, session
    )

    station_list_adapter = TypeAdapter(list[Station])
    stations = station_list_adapter.validate_python(stations_rows)

    original_route_length = get_route_length(directions_response)
    assign_segment_ids(stations, original_route_length, settings.SEGMENT_LENGTH_M)

    unique_networks_ids = get_unique_network_ids(stations)
    fuel_prices = await fetch_fuel_prices(unique_networks_ids, data.fuel_type, session)

    fuel_prices_dict = map_fuel_prices_to_dict(fuel_prices)
    stations = merge_stations_and_prices(stations, fuel_prices_dict)

    osrm = OSRMClient(osrm_client)
    stations_coordinates = get_stations_coordinates_dicts(stations)
    forward_matrix = await osrm.get_table(
        data.start.model_dump(), stations_coordinates, MatrixDirection.FORWARD
    )
    forward_distances = get_matrix_distances(forward_matrix)
    forward_durations = get_matrix_durations(forward_matrix)

    backward_matrix = await osrm.get_table(
        data.end.model_dump(), stations_coordinates, MatrixDirection.BACKWARD
    )
    backward_distances = get_matrix_distances(backward_matrix)
    backward_durations = get_matrix_durations(backward_matrix)

    distances_list = merge_matrixes(forward_distances, backward_distances)
    durations_list = merge_matrixes(forward_durations, backward_durations)

    add_total_distances_and_durations(stations, distances_list, durations_list)

    original_route_duration = get_route_duration(directions_response)
    calculate_stations_metrics(
        stations,
        original_route_length,
        original_route_duration,
        data.volume,
        data.fuel_consumption,
        data.income_per_minute,
    )

    top_stations = get_top_stations_for_segment(
        stations, settings.MAX_STATIONS_PET_NETWORK
    )

    original_route = SimpleRoute(
        geometry=GeoJSONLineString(
            coordinates=original_route_coordinates
        ),
        distance=original_route_length,
        duration=original_route_duration,
    )

    return {
        "original_route": original_route,
        "stations": top_stations
    }


@router.post(
    "/detailed-routes",
    response_model=DetailedRoutesResponse,
    status_code=status.HTTP_200_OK
)
async def get_detailed_routes(
        coordinates: DetailedRoutesRequest,
        mapbox_client: AsyncClient = Depends(get_mapbox_client),
):
    mapbox = MapboxClient(mapbox_client)
    directions_params = DirectionsParams()
    directions_params.setup_full_request()

    tasks = [
        mapbox.get_direction(
            [
                coordinates.start.model_dump(),
                station.model_dump(),
                coordinates.end.model_dump()
            ],
            directions_params
        )
        for station in coordinates.stations
    ]

    responses = await asyncio.gather(*tasks)

    routes = [
        DetailedRoute.model_validate(response["routes"][0])
        for response in responses
    ]

    return {
        "routes": routes
    }
