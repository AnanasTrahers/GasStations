from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError

from src import routers
from src.api.middleware import LogIdMiddleware
from src.config import project_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    httpx_client = httpx.AsyncClient()
    redis_client = Redis.from_url(project_settings.REDIS_URL, decode_responses=True)

    yield {
        "httpx_client": httpx_client,
        "redis_client": redis_client,
    }

    await redis_client.aclose()
    await httpx_client.aclose()


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
