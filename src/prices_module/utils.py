import asyncio

from tenacity import RetryCallState

from src.prices_module.settings import scraper_settings
from src.utils.logs import Logger


async def run_parser(callable_):
    return await asyncio.get_running_loop().run_in_executor(
        scraper_settings.PARSERS_THREAD_EXECUTOR,
        callable_,
    )


def tenacity_log_before(retry_state: RetryCallState):
    Logger.info()
