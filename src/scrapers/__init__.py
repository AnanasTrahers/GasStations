from src.scrapers.base import BaseScraper
from src.scrapers.minfin import MinfinScraper
from src.scrapers.types import FuelPriceRecord, ScrapingResult
from src.scrapers.vseazs import VseazsScraper

__all__ = [
    "BaseScraper",
    "FuelPriceRecord",
    "MinfinScraper",
    "ScrapingResult",
    "VseazsScraper",
]
