"""CLI to kick off an ETL run — the replacement for Airflow's "trigger DAG" button.

    # enqueue onto Redis, a running worker picks it up
    uv run python -m src.worker.trigger fuel_prices_etl
    uv run python -m src.worker.trigger fuel_prices_etl --region KYIV
    uv run python -m src.worker.trigger gas_stations_import

    # run the pipeline inline instead: no Redis, no worker, useful for debugging
    uv run python -m src.worker.trigger fuel_prices_etl --now
"""

import argparse
import asyncio

from src.config import LOG_ID
from src.prices_module.enums import RegionEnum
from src.utils.logs import Logger
from src.utils.order import get_uuid_str
from src.worker import jobs
from src.worker.pool import create_arq_pool
from src.worker.settings import on_shutdown, on_startup

JOB_NAMES = (jobs.JOB_FUEL_PRICES, jobs.JOB_GAS_STATIONS)


async def _run_inline(job_name: str, region: str) -> None:
    # Seed the correlation id up front, the way the worker's on_job_start does:
    # otherwise each gathered extract lazily mints its own and the run's log
    # lines can't be tied together.
    LOG_ID.set(get_uuid_str())

    ctx: dict = {}
    await on_startup(ctx)
    try:
        if job_name == jobs.JOB_FUEL_PRICES:
            result = await jobs.fuel_prices_etl(ctx, region=region)
        else:
            result = await jobs.gas_stations_import(ctx)
        Logger.info(f"[trigger] {job_name} finished inline", result=result)
    finally:
        await on_shutdown(ctx)


async def _enqueue(job_name: str, region: str) -> None:
    pool = await create_arq_pool()
    try:
        if job_name == jobs.JOB_FUEL_PRICES:
            job = await pool.enqueue_job(job_name, region=region)
        else:
            job = await pool.enqueue_job(job_name)

        if job is None:
            Logger.warning(
                f"[trigger] {job_name} not enqueued — "
                f"a job with the same id already exists"
            )
            return
        Logger.info(f"[trigger] enqueued {job_name}", job_id=job.job_id)
    finally:
        await pool.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", choices=JOB_NAMES)
    parser.add_argument(
        "--region",
        choices=[r.value for r in RegionEnum],
        default=RegionEnum.KYIV.value,
        help=f"only used by {jobs.JOB_FUEL_PRICES}",
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="run the pipeline in this process instead of enqueueing it",
    )
    args = parser.parse_args()

    if args.now:
        asyncio.run(_run_inline(args.job, args.region))
    else:
        asyncio.run(_enqueue(args.job, args.region))


if __name__ == "__main__":
    main()
