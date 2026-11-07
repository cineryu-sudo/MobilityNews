"""
Crawlers module for fetching news from various sources.
"""

from .base import Article, BaseCrawler
from .techcrunch import TechCrunchCrawler
from .autonews import AutoNewsCrawler
from .etnews import ETNewsCrawler
from .hackernews import HackerNewsCrawler
from .rss import (
    AutoDailyCrawler,
    AutoHeraldCrawler,
    FleetOwnerCrawler,
    TelematicsWireCrawler,
    TheVergeCrawler,
    ZDNetKoreaCrawler,
)
from .digitaltoday import DigitalTodayCrawler

__all__ = [
    "Article",
    "BaseCrawler",
    "TechCrunchCrawler",
    "TheVergeCrawler",
    "AutoNewsCrawler",
    "ETNewsCrawler",
    "AutoDailyCrawler",
    "HackerNewsCrawler",
    "TelematicsWireCrawler",
    "ZDNetKoreaCrawler",
    "FleetOwnerCrawler",
    "DigitalTodayCrawler",
    "AutoHeraldCrawler",
]
