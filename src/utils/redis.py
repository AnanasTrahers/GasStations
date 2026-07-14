import json

from redis.asyncio import Redis

from src.config import business_settings

FUEL_TYPES_KEY = "fuel_types"


async def get_cached_fuel_types(redis: Redis) -> list[str] | None:
    cached = await redis.get(FUEL_TYPES_KEY)
    if cached is None:
        return None
    return json.loads(cached)


async def set_cached_fuel_types(redis: Redis, fuel_types: list[str]) -> None:
    await redis.set(
        FUEL_TYPES_KEY,
        json.dumps(sorted(fuel_types)),
        ex=business_settings.FUEL_TYPES_CACHE_TTL
    )
