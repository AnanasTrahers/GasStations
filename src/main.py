from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError

from src import routers
from src.api import admin_router
from src.api.middleware import LogIdMiddleware
from src.config import project_settings
from src.utils.logs import Logger
from src.worker.pool import create_arq_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    httpx_client = httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(retries=3),
        limits=httpx.Limits(max_keepalive_connections=0),
        timeout=httpx.Timeout(10.0)
    )
    redis_client = Redis.from_url(project_settings.REDIS_URL, decode_responses=True)

    # Separate connection from redis_client above: arq speaks bytes, so it cannot
    # share a decode_responses=True client. Only the admin endpoints need it, so a
    # dead queue must not stop the optimization API from serving.
    try:
        arq_pool = await create_arq_pool()
    except Exception as exc:
        Logger.error("Could not open the arq pool; job endpoints disabled", error=exc)
        arq_pool = None

    yield {
        "httpx_client": httpx_client,
        "redis_client": redis_client,
        "arq_pool": arq_pool,
    }

    if arq_pool is not None:
        await arq_pool.aclose()
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
app.include_router(admin_router.router)

app.add_middleware(LogIdMiddleware)


if __name__ == '__main__':
    uvicorn.run(app)
