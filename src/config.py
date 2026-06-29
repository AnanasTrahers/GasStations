from pathlib import Path
from contextvars import ContextVar
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_ID: ContextVar[str] = ContextVar("LOG_ID", default="")


class Settings(BaseSettings):
    DATABASE_URL: str

    MAPBOX_API_KEY: str
    MAPBOX_BASE_URL: str # why?
    MAPBOX_DIRECTIONS_ENDPOINT: str
    MAPBOX_MATRIX_ENDPOINT: str
    MAPBOX_ISOCHRONE_ENDPOINT: str
    OSRM_BASE_URL: str
    OSRM_TABLE_ENDPOINT: str

    FUEL_PRICE_SAFE_DAYS: int
    BUFFER_RADIUS_M: int
    SEGMENT_LENGTH_M: int
    ON_ROUTE_MAX_STATIONS_PER_NETWORK: int
    NEARBY_MAX_STATIONS_PER_NETWORK: int
    ISOCHRONE_CONTOURS_MINUTES: int

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        extra="ignore"
    )


settings = Settings()
