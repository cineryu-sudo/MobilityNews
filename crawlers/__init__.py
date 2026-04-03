"""
Crawlers module for fetching news from various sources.
"""

from .base import Article, BaseCrawler
from .techcrunch import TechCrunchCrawler
from .theverge import TheVergeCrawler
from .autonews import AutoNewsCrawler
from .etnews import ETNewsCrawler
from .autodaily import AutoDailyCrawler
from .hackernews import HackerNewsCrawler
from .rss import TelematicsWireCrawler, ZDNetKoreaCrawler, FleetOwnerCrawler
from .digitaltoday import DigitalTodayCrawler
from .autoherald import AutoHeraldCrawler

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
