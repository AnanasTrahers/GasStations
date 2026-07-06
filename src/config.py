from email.policy import default
from pathlib import Path
from contextvars import ContextVar
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_ID: ContextVar[str] = ContextVar("LOG_ID")


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
    MAX_STATIONS_PET_NETWORK: int

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        extra="ignore"
    )


settings = Settings()
