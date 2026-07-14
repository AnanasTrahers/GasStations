import httpx
from fastapi import Request, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.database import get_db
from src.repositories import DBRepository


def get_httpx_client(request: Request) -> httpx.AsyncClient:
    return getattr(request.state, "httpx_client")


def get_redis(request: Request) -> Redis:
    return getattr(request.state, "redis_client")


def get_db_repo(session: AsyncSession = Depends(get_db)) -> DBRepository:
    return DBRepository(session)
