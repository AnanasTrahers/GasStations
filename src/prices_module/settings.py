import asyncio
from concurrent.futures import ThreadPoolExecutor


class ScrapersSettings:
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    DEFAULT_TIMEOUT = 30.0
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 1.5  # seconds; multiplied by 2^n on each attempt

    VSEAZS_CONCURRENCY = 4

    PARSERS_THREAD_EXECUTOR = ThreadPoolExecutor(max_workers=4)

    OVERPASS_TIMEOUT = 240.0

    def __init__(self) -> None:
        self._vseazs_limiter: asyncio.Semaphore | None = None

    @property
    def VSEAZS_LIMITER(self) -> asyncio.Semaphore:
        """Bound simultaneous POSTs to vseazs.com.

        Created lazily rather than at import time: a semaphore built before any
        event loop exists binds to whichever loop first awaits it, which would
        break the moment a second ``asyncio.run`` ran in the same process.
        """
        if self._vseazs_limiter is None:
            self._vseazs_limiter = asyncio.Semaphore(self.VSEAZS_CONCURRENCY)
        return self._vseazs_limiter


scraper_settings = ScrapersSettings()
