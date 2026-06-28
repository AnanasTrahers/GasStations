import os
from pathlib import Path
from contextvars import ContextVar
from pydantic_settings import BaseSettings, SettingsConfigDict
from infisical_sdk import InfisicalSDKClient
from dotenv import load_dotenv
load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_ID: ContextVar[str] = ContextVar("LOG_ID", default="")


client = InfisicalSDKClient(
    host="https://app.infisical.com",
    cache_ttl=None
)

client.auth.universal_auth.login(
    client_id=os.getenv("INFISICAL_CLIENT_ID"),
    client_secret=os.getenv("INFISICAL_CLIENT_SECRET")
)
# client.auth.token_auth.login(os.getenv("INFISICAL_TOKEN"))

secrets = client.secrets.list_secrets(
    project_id=os.getenv("INFISICAL_PROJECT_ID"),
    environment_slug="dev",
    secret_path="/"
)

print(secrets)
print(type(secrets))



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


