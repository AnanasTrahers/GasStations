"""arq worker configuration — replaces the Airflow scheduler + DAG processor.

Run it with::

    uv run arq src.worker.settings.WorkerSettings

No ``--env-file`` is needed: ``ProjectSettings`` reads ``.env`` directly through
pydantic, unlike the Airflow CLI which only honoured real process env vars.
"""

from datetime import UTC

import httpx
from arq import cron
from arq.connections import RedisSettings

from src.config import LOG_ID, project_settings
from src.database import engine
from src.prices_module.settings import scraper_settings
from src.worker import jobs


async def on_startup(ctx: dict) -> None:
    """Build the client the jobs borrow, mirroring the FastAPI lifespan."""
    ctx["httpx_client"] = httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(retries=3),
        timeout=httpx.Timeout(scraper_settings.DEFAULT_TIMEOUT),
        headers={"User-Agent": scraper_settings.DEFAULT_USER_AGENT},
        follow_redirects=True,
    )


async def on_shutdown(ctx: dict) -> None:
    await ctx["httpx_client"].aclose()
    # The engine is created at import time and nothing else disposes it; a
    # long-lived worker has to hand its pooled connections back on exit.
    await engine.dispose()


async def on_job_start(ctx: dict) -> None:
    """Correlate every log line of a run, the way LogIdMiddleware does per request."""
    LOG_ID.set(ctx["job_id"])


class WorkerSettings:
    functions = [jobs.fuel_prices_etl, jobs.gas_stations_import]

    cron_jobs = [
        # was: dags/prices_dag.py schedule="0 6 * * *"
        cron(jobs.fuel_prices_etl, hour=6, minute=0, max_tries=3, timeout=600),
        # was: dags/stations_dag.py schedule="0 4 * * 0"
        # Overpass allows itself 240s per request (OVERPASS_TIMEOUT) and tenacity
        # retries it 3x, so this needs far more than arq's 300s default.
        cron(
            jobs.gas_stations_import,
            weekday="sun",
            hour=4,
            minute=0,
            max_tries=3,
            timeout=900,
        ),
    ]

    redis_settings = RedisSettings.from_dsn(project_settings.REDIS_URL)

    on_startup = on_startup
    on_shutdown = on_shutdown
    on_job_start = on_job_start

    # The Airflow DAGs ran on UTC (AIRFLOW__CORE__DEFAULT_TIMEZONE was never set),
    # so cron stays on UTC to keep the schedules where they were.
    timezone = UTC

    max_jobs = 4
    job_timeout = 900
    max_tries = 3
    keep_result = 3600

    # arq expires the health key after interval + 1s, so the 3600s default is
    # useless for `arq --check` as a container healthcheck.
    health_check_interval = 30
