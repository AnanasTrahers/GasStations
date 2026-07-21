import json
import time
from datetime import datetime, timezone, timedelta

import httpx
import jwt

from src.config import project_settings
from src.utils.logs import LoggerMixin

_sa_raw = json.loads(project_settings.GOOGLE_PLAY_SERVICE_ACCOUNT_KEY)
try:
    _SA_EMAIL = _sa_raw["client_email"]
    _SA_PRIVATE_KEY = _sa_raw["private_key"]
    _SA_PRIVATE_KEY_ID = _sa_raw["private_key_id"]
    _SA_TOKEN_URI = _sa_raw.get("token_uri", "https://oauth2.googleapis.com/token")
except KeyError as e:
    raise ValueError(f"Missing required field in GOOGLE_PLAY_SERVICE_ACCOUNT_KEY: {e}") from e


class GooglePlayClient(LoggerMixin):
    API_BASE = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.package_name = project_settings.GOOGLE_PLAY_PACKAGE_NAME
        self._access_token: str | None = None
        self._token_expiry: datetime | None = None

    def _build_jwt_assertion(self) -> str:
        now = int(time.time())
        payload = {
            "iss": _SA_EMAIL,
            "scope": "https://www.googleapis.com/auth/androidpublisher",
            "aud": _SA_TOKEN_URI,
            "iat": now,
            "exp": now + 3600,
        }
        headers = {"kid": _SA_PRIVATE_KEY_ID}

        return jwt.encode(payload, _SA_PRIVATE_KEY, algorithm="RS256", headers=headers)

    async def _refresh_access_token(self) -> None:
        assertion = self._build_jwt_assertion()
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }

        try:
            resp = await self.client.post(_SA_TOKEN_URI, data=data)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.log_error(f"Token request failed: {e.response.status_code}")
            raise
        except httpx.RequestError:
            self.log_error("Network error while fetching Google Play access token")
            raise

        try:
            token_data = resp.json()
        except ValueError:
            self.log_error("Invalid JSON response from token endpoint")
            raise

        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)

    async def _get_access_token(self) -> str:
        if (
                self._access_token is not None
                and self._token_expiry is not None
                and datetime.now(timezone.utc) < self._token_expiry
        ):
            return self._access_token

        await self._refresh_access_token()
        return self._access_token

    async def verify_purchase_token(
            self, product_id: str, purchase_token: str
    ) -> dict:
        token = await self._get_access_token()

        url = (
            f"{self.API_BASE}/{self.package_name}"
            f"/purchases/subscriptionsv2/tokens/{purchase_token}"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        self.log_info(f"Verifying purchase token for {self.package_name}")
        try:
            resp = await self.client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.log_error(f"Purchase verification failed: {e.response.status_code}")
            raise
        except httpx.RequestError:
            self.log_error("Network error while verifying purchase")
            raise

        try:
            return resp.json()
        except ValueError:
            self.log_error("Invalid JSON from Google Play verification response")
            raise

    async def acknowledge_purchase(self, purchase_token: str) -> None:
        token = await self._get_access_token()

        url = (
            f"{self.API_BASE}/{self.package_name}"
            f"/purchases/subscriptionsv2/tokens/{purchase_token}:acknowledge"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        self.log_info(f"Acknowledging purchase for {self.package_name}")
        try:
            resp = await self.client.post(url, headers=headers, json={})
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.log_error(f"Acknowledge failed: {e.response.status_code}")
            raise
        except httpx.RequestError:
            self.log_error("Network error while acknowledging purchase")
            raise
