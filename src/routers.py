import asyncio

from fastapi import APIRouter, status, Depends, Header, Response
from fastapi.responses import JSONResponse
from httpx import AsyncClient
from pydantic import TypeAdapter
from redis.asyncio import Redis

from src.clients.mapbox import MapboxClient
from src.clients.osrm import OsrmClient
from src.config import business_settings
from src.dependencies import get_httpx_client, get_db_repo, get_redis
from src.repositories import DBRepository
from src.schemas import (
    OnRouteStationsResponse,
    OnRouteStationsRequest,
    DirectionsParams,
    OnRouteStation,
    DetailedRoutesResponse,
    DetailedRoutesRequest,
    DetailedRoute,
    NearbyStationsRequest,
    NearbyStationsResponse,
    NearbyStation,
    FuelTypesResponse,
)
from src.service import (
    assign_segment_ids,
    calculate_on_route_stations_metrics,
    get_top_on_route_stations,
    calculate_nearby_stations_metrics,
    get_top_nearby_stations,
    fetch_and_merge_fuel_prices,
    get_and_apply_matrices,
    fetch_and_build_simple_route,
    fetch_and_build_polygon_wkt,
    fetch_osrm_route_metrics,
    fetch_fuel_types
)
from src.utils.etag import generate_etag, check_etag_match
from src.utils.logs import Logger
from src.utils.wkt_builders import get_route_wkt

router = APIRouter(prefix="/v1/optimization", tags=["Stations"])


@router.get(
    "/fuel-types",
    response_model=FuelTypesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_fuel_types(
        if_none_match: str | None = Header(default=None),
        db_repo: DBRepository = Depends(get_db_repo),
        redis: Redis = Depends(get_redis),
):
    Logger.info("Fetching fuel types...")

    fuel_types = await fetch_fuel_types(redis, db_repo)
    etag = generate_etag(fuel_types)

    if check_etag_match(if_none_match, etag):
        Logger.info("ETag match - returning 304")
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    Logger.info(f"Returning {len(fuel_types)} fuel types")
    return JSONResponse(
        content={"fuel_types": fuel_types},
        headers={
            "ETag": etag,
            "Cache-Control": "no-cache"
        }
    )


@router.post(
    "/on-route",
    response_model=OnRouteStationsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_on_route_stations(
        data: OnRouteStationsRequest,
        db_repo: DBRepository = Depends(get_db_repo),
        httpx_client: AsyncClient = Depends(get_httpx_client)
):
    Logger.info("Starting on-route optimization request...")

    # 1. Fetch Route
    mapbox = MapboxClient(httpx_client)
    original_route = await fetch_and_build_simple_route(mapbox, data.start, data.end)

    # 2. Fetch Stations
    route_wkt = get_route_wkt(original_route.geometry.coordinates)
    stations_rows = await db_repo.stations.fetch_on_route(
        route_wkt, business_settings.BUFFER_RADIUS_M
    )
    stations = TypeAdapter(list[OnRouteStation]).validate_python(stations_rows)

    if not stations:
        return {
            "original_route": original_route,
            "stations": []
        }

    assign_segment_ids(stations, original_route.distance, business_settings.SEGMENT_LENGTH_M)

    # 3. Parallelize Prices & OSRM Matrices
    osrm = OsrmClient(httpx_client)
    osrm_distance, osrm_duration = await fetch_osrm_route_metrics(osrm, data.start, data.end)

    await asyncio.gather(
        fetch_and_merge_fuel_prices(stations, data.fuel_type, db_repo),
        get_and_apply_matrices(stations, osrm, data.start.model_dump(), data.end.model_dump())
    )

    # 4. Finalize Metrics
    stations = calculate_on_route_stations_metrics(
        stations,
        osrm_distance,
        osrm_duration,
        data.volume,
        data.fuel_consumption,
        data.income_per_minute,
        business_settings.MAX_EXTRA_TIME_S,
    )
    top_stations = get_top_on_route_stations(
        stations, business_settings.ON_ROUTE_MAX_STATIONS_PER_NETWORK
    )

    Logger.info(f"Completed on-route optimization. Returning {len(top_stations)} stations")
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

    mapbox = MapboxClient(httpx_client)
    directions_params = DirectionsParams.setup_full_request()

    tasks = [
        mapbox.get_direction(
            [
                coordinates.start.model_dump(),
                station.model_dump(),
                coordinates.end.model_dump()
            ],
            directions_params
        )
        for station in coordinates.stations_coordinates
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
        db_repo: DBRepository = Depends(get_db_repo),
        httpx_client: AsyncClient = Depends(get_httpx_client)
):
    Logger.info("Starting nearby optimization request...")

    # 1. Fetch Isochrone Polygon
    mapbox = MapboxClient(httpx_client)
    polygon_wkt = await fetch_and_build_polygon_wkt(mapbox, data.start)

    # 2. Fetch Stations
    stations_rows = await db_repo.stations.fetch_nearby(polygon_wkt)
    stations = TypeAdapter(list[NearbyStation]).validate_python(stations_rows)

    if not stations:
        return {"stations": []}

    # 3. Parallelize Prices & OSRM Matrices
    osrm = OsrmClient(httpx_client)
    await asyncio.gather(
        fetch_and_merge_fuel_prices(stations, data.fuel_type, db_repo),
        get_and_apply_matrices(stations, osrm, data.start.model_dump(), data.start.model_dump())
    )

    # 4. Finalize Metrics
    stations = calculate_nearby_stations_metrics(
        stations,
        data.volume,
        data.fuel_consumption,
        data.income_per_minute
    )
    top_stations = get_top_nearby_stations(
        stations, business_settings.NEARBY_MAX_STATIONS_PER_NETWORK
    )

    Logger.info(f"Completed nearby optimization. Returning {len(top_stations)} stations")
    return {
        "stations": top_stations
    }
