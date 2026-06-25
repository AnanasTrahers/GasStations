from contextlib import asynccontextmanager
from fastapi import FastAPI
import httpx

from src import routers
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    mapbox_client = httpx.AsyncClient(base_url=settings.MAPBOX_BASE_URL)
    osrm_client = httpx.AsyncClient(base_url=settings.OSRM_BASE_URL)

    yield {
        "mapbox_client": mapbox_client,
        "osrm_client": osrm_client
    }

    await mapbox_client.aclose()
    await osrm_client.aclose()


app = FastAPI(lifespan=lifespan)

app.include_router(routers.router)
