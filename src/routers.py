import asyncio

from fastapi import APIRouter, status, Depends
from httpx import AsyncClient
from sqlalchemy.ext.asyncio.session import AsyncSession
from pydantic import TypeAdapter

from src.clients.mapbox import MapboxHTTPXClient
from src.clients.osrm import OSRMHTTPXClient
from src.config import settings
from src.database import get_db
from src.dependencies import get_httpx_client
from src.schemas import (
    OnRouteStationsResponse,
    OnRouteStationsRequest,
    DirectionsParams,
    OnRouteStation,
    SimpleRoute,
    GeoJSONLineString,
    DetailedRoutesResponse,
    DetailedRoutesRequest,
    DetailedRoute,
    NearbyStationsRequest,
    NearbyStationsResponse,
    NearbyStation,
)
from src.service import (
    fetch_on_route_stations,
    assign_segment_ids,
    calculate_on_route_stations_metrics,
    get_top_on_route_stations,
    fetch_nearby_stations,
    calculate_nearby_stations_metrics,
    get_top_nearby_stations,
    fetch_and_merge_fuel_prices,
    get_and_apply_matrices
)
from src.utils.response_helpers import (
    get_route_coordinates,
    get_route_length,
    get_route_duration,
    get_polygon
)
from src.utils.wkt_builders import get_route_wkt, get_polygon_wkt
from src.utils.logs import Logger

router = APIRouter(prefix="/v1/optimization", tags=["Stations"])


@router.post(
    "/on-route",
    response_model=OnRouteStationsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_on_route_stations(
        data: OnRouteStationsRequest,
        session: AsyncSession = Depends(get_db),
        httpx_client: AsyncClient = Depends(get_httpx_client)
):
    Logger.info("Starting on-route optimization request...")

    mapbox = MapboxHTTPXClient(httpx_client)
    directions_params = DirectionsParams()
    directions_response = await mapbox.get_direction(
        [data.start.model_dump(), data.end.model_dump()], directions_params
    )

    original_route_coordinates = get_route_coordinates(directions_response)
    original_route_wkt = get_route_wkt(original_route_coordinates)
    stations_rows = await fetch_on_route_stations(
        original_route_wkt, settings.BUFFER_RADIUS_M, session
    )

    stations = TypeAdapter(list[OnRouteStation]).validate_python(stations_rows)

    original_route_length = get_route_length(directions_response)
    assign_segment_ids(stations, original_route_length, settings.SEGMENT_LENGTH_M)

    stations = await fetch_and_merge_fuel_prices(stations, data.fuel_type, session)

    osrm = OSRMHTTPXClient(httpx_client)
    await get_and_apply_matrices(
        stations, osrm, data.start.model_dump(), data.end.model_dump()
    )

    original_route_duration = get_route_duration(directions_response)
    calculate_on_route_stations_metrics(
        stations,
        original_route_length,
        original_route_duration,
        data.volume,
        data.fuel_consumption,
        data.income_per_minute,
    )

    top_stations = get_top_on_route_stations(
        stations, settings.ON_ROUTE_MAX_STATIONS_PER_NETWORK
    )

    original_route = SimpleRoute(
        geometry=GeoJSONLineString(
            coordinates=original_route_coordinates
        ),
        distance=original_route_length,
        duration=original_route_duration,
    )

    Logger.info(
        f"Completed on-route optimization. Returning {len(stations)} stations"
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
        httpx_client: AsyncClient = Depends(get_httpx_client),
):
    Logger.info(
        f"Generating detailed routes for {len(coordinates.stations_coordinates)} stations..."
    )

    mapbox = MapboxHTTPXClient(httpx_client)
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

    Logger.info("Completed detailed routes generation")
    return {
        "routes": routes
    }


@router.post(
    "/nearby",
    response_model=NearbyStationsResponse,
    status_code=status.HTTP_200_OK
)
async def get_nearby_stations(
        data: NearbyStationsRequest,
        session: AsyncSession = Depends(get_db),
        httpx_client: AsyncClient = Depends(get_httpx_client)
):
    Logger.info("Starting nearby optimization request...")

    mapbox = MapboxHTTPXClient(httpx_client)
    isochrones_response = await mapbox.get_isochrone(data.start.model_dump())
    polygon = get_polygon(isochrones_response)
    polygon_wkt = get_polygon_wkt(polygon)

    stations_rows = await fetch_nearby_stations(polygon_wkt, session)
    stations = TypeAdapter(list[NearbyStation]).validate_python(stations_rows)

    stations = await fetch_and_merge_fuel_prices(stations, data.fuel_type, session)

    osrm = OSRMHTTPXClient(httpx_client)
    await get_and_apply_matrices(
        stations, osrm, data.start.model_dump(), data.start.model_dump()
    )

    calculate_nearby_stations_metrics(
        stations,
        data.volume,
        data.fuel_consumption,
        data.income_per_minute,
    )

    top_stations = get_top_nearby_stations(
        stations, settings.NEARBY_MAX_STATIONS_PER_NETWORK
    )

    Logger.info(
        f"Completed nearby optimization. Returning {len(stations)} stations"
    )
    return top_stations
