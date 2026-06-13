from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    DATABASE_URL: str

    MAPBOX_API_KEY: str
    MAPBOX_BASE_URL: str
    MAPBOX_DIRECTIONS_ENDPOINT: str
    MAPBOX_MATRIX_ENDPOINT: str
    MAPBOX_ISOCHRONE_ENDPOINT: str

    FUEL_PRICE_SAFE_DAYS: int

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        extra="ignore"
    )


settings = Settings()
