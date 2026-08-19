from pathlib import Path
from contextvars import ContextVar
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_ID: ContextVar[str] = ContextVar("LOG_ID")


class ProjectSettings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    MAPBOX_API_KEY: str

    ENVIRONMENT: str = "development"
    ALLOWED_HOSTS: list[str] = ["*"]

    DB_ECHO: bool = False
    """Log every statement. Off by default — the arq worker bulk-upserts hundreds
    of rows per run and would otherwise drown its own logs in SQL."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        extra="ignore"
    )


class BusinessSettings(BaseSettings):
    FUEL_PRICE_SAFE_DAYS: int = 7
    BUFFER_RADIUS_M: int = 2000
    SEGMENT_LENGTH_M: int = 50000
    ON_ROUTE_MAX_STATIONS_PER_NETWORK: int = 1
    NEARBY_MAX_STATIONS_PER_NETWORK: int = 2
    ISOCHRONE_CONTOURS_MINUTES: int = 10
    MAX_EXTRA_TIME_S: int = 600
    FUEL_TYPES_CACHE_TTL: int = 60 * 60 * 6


project_settings = ProjectSettings()
business_settings = BusinessSettings()
