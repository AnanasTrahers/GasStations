from fastapi import Request
import httpx


def get_mapbox_client(request: Request) -> httpx.AsyncClient:
    return getattr(request.state, "mapbox_client")

def get_osrm_client(request: Request) -> httpx.AsyncClient:
    return getattr(request.state, "osrm_client")
