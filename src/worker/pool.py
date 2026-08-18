"""arq Redis pool used to enqueue jobs from outside the worker."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from src.config import project_settings


async def create_arq_pool() -> ArqRedis:
    """Open a pool for enqueueing jobs.

    arq speaks raw bytes, so this must never reuse the app's
    ``Redis.from_url(..., decode_responses=True)`` client.
    """
    return await create_pool(
        RedisSettings.from_dsn(project_settings.REDIS_URL)
    )
