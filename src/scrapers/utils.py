import asyncio

from src.scrapers.settings import scraper_settings


async def run_parser(callable_):
    return await asyncio.get_running_loop().run_in_executor(
        scraper_settings.PARSERS_THREAD_EXECUTOR,
        callable_,
    )