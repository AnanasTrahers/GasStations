import httpx
from arq.connections import ArqRedis
from fastapi import Request, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.database import get_db
from src.repositories import DBRepository


def get_httpx_client(request: Request) -> httpx.AsyncClient:
    return getattr(request.state, "httpx_client")


def get_redis(request: Request) -> Redis:
    return getattr(request.state, "redis_client")


def get_arq_pool(request: Request) -> ArqRedis:
    pool: ArqRedis | None = getattr(request.state, "arq_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The job queue is currently unreachable. Please try again later.",
        )
    return pool


def get_db_repo(session: AsyncSession = Depends(get_db)) -> DBRepository:
    return DBRepository(session)

