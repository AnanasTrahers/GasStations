"""Base scraper with shared HTTP client, retry logic, and error handling."""

import asyncio
from datetime import date
from typing import Optional

import httpx

from src.scrapers.settings import scraper_settings
from src.scrapers.types import ScrapingResult
from src.utils.logs import LoggerMixin


class ScrapingError(Exception):
    """Non-retryable error during scraping (e.g. parse failure)."""


class BaseScraper(LoggerMixin):
    """Shared scaffolding for HTTP scrapers.

    Provides an ``httpx.AsyncClient`` instance, exponential-backoff retry
    on transient HTTP errors, and a ``scrape()`` entry point that
    subclasses must implement.
    """

    source: str = "base"
    """Identifier used in ``FuelPriceRecord.source``."""

    base_url: str = ""
    """Root URL of the target site (used for building absolute links)."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    # ── HTTP helpers ────────────────────────────────────────────────

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(scraper_settings.DEFAULT_TIMEOUT),
                headers={"User-Agent": scraper_settings.DEFAULT_USER_AGENT},
                follow_redirects=True,
            )
        return self._client

    async def _get(self, url: str, **kwargs) -> httpx.Response:
        return await self._retry("GET", url, **kwargs)

    async def _post(self, url: str, **kwargs) -> httpx.Response:
        return await self._retry("POST", url, **kwargs)

    async def _retry(
            self, method: str, url: str, **kwargs
    ) -> httpx.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(scraper_settings.MAX_RETRIES + 1):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if attempt < scraper_settings.MAX_RETRIES and exc.response.status_code >= 500:
                    delay = scraper_settings.RETRY_BACKOFF_BASE * (2 ** attempt)
                    self.log_warning(
                        "%s %s → %s, retry %d/%d in %.1fs".format(
                            method,
                            url,
                            exc.response.status_code,
                            attempt + 1,
                            scraper_settings.MAX_RETRIES,
                            delay,
                        )
                    )
                    await asyncio.sleep(delay)
                    last_exc = exc
                    continue
                raise
            except httpx.RequestError as exc:
                if attempt < scraper_settings.MAX_RETRIES:
                    delay = scraper_settings.RETRY_BACKOFF_BASE * (2 ** attempt)
                    self.log_warning(
                        "%s %s request error: %s, retry %d/%d in %.1fs".format(
                        method,
                        url,
                        exc,
                        attempt + 1,
                        scraper_settings.MAX_RETRIES,
                        delay,
                    ))
                    await asyncio.sleep(delay)
                    last_exc = exc
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    # ── cleanup ─────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
