from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import httpx

from src import routers
from src.api.middleware import LogIdMiddleware
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


@app.exception_handler(httpx.HTTPError)
async def external_routing_api_handler(request: Request, exc: httpx.HTTPError):
    return JSONResponse(
        status_code=502,
        content={"detail": "The routing service is temporarily unavailable. Please try again."},
    )


@app.exception_handler(SQLAlchemyError)
async def database_offline_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is currently unreachable. Please try again later."},
    )


app.include_router(routers.router)

app.add_middleware(LogIdMiddleware)
