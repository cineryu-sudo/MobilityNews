import unittest
from datetime import date
from unittest.mock import patch

from bs4 import BeautifulSoup

from config import NEWS_SOURCES
from crawlers import AutoDailyCrawler, AutoHeraldCrawler, FleetOwnerCrawler, TheVergeCrawler
from crawlers.base import Article, ContentFetcher
from intelligence.filter import ArticleFilter

FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>feed</title>
<item>
  <title>샘플 기사 제목입니다</title>
  <link>https://example.com/news/articleView.html?idxno=1</link>
  <pubDate>Sat, 07 Nov 2026 09:12:04 +0900</pubDate>
</item>
</channel></rss>"""


def _article(title, source="TechCrunch", language="en"):
    return Article(title=title, url="https://example.com/a", source=source, language=language)


class PriorityRuleTests(unittest.TestCase):
    def setUp(self):
        self.article_filter = ArticleFilter(content_fetcher=lambda _url: "")

    def _bucket(self, title, **kwargs):
        return self.article_filter._classify_priority(_article(title, **kwargs))[0]

    def test_plural_mobility_terms_count_as_mobility_signal(self):
        self.assertGreater(self._bucket("When electric cars were for women"), 0)

    def test_ev_plural_counts_as_mobility_signal(self):
        self.assertGreater(self._bucket("Which party ran against EVs this year"), 0)

    def test_vehicle_maker_name_counts_as_mobility_signal(self):
        self.assertGreater(self._bucket("Tesla will stop making the Cybertruck in 2027"), 0)

    def test_korean_vehicle_maker_name_counts_as_mobility_signal(self):
        title = '"안팔려서…" 테슬라, 2027년 중반 사이버트럭 생산 종료 수순'
        self.assertGreater(self._bucket(title, source="디지털투데이", language="ko"), 0)

    def test_autonomy_counts_as_mobility_signal(self):
        self.assertGreater(self._bucket("Startup bets on autonomy this year"), 0)

    def test_non_mobility_conglomerate_news_stays_excluded(self):
        title = "엔비디아, 네이버에 1.3조원 납입…‘AI 팩토리’ 물살"
        self.assertEqual(self._bucket(title, source="zdnet_korea", language="ko"), 0)

    def test_telecom_only_news_stays_excluded(self):
        title = "플렌티넷 모아진 LG유플러스 가입자 20만 돌파"
        self.assertEqual(self._bucket(title, source="전자신문", language="ko"), 0)

    def test_short_terms_do_not_match_inside_other_words(self):
        self.assertEqual(self._bucket("Every carton of events scares evil scars"), 0)


class ArticleContentTests(unittest.TestCase):
    def _extract(self, html):
        fetcher = ContentFetcher()
        with patch.object(fetcher, "_get_soup", return_value=BeautifulSoup(html, "html.parser")):
            return fetcher.fetch_article_content("https://example.com/a")

    def test_skips_empty_leading_article_tag(self):
        html = """<html><body>
          <article class="item">메뉴</article>
          <article class="body"><p>실제 기사 본문입니다.</p></article>
        </body></html>"""
        self.assertEqual(self._extract(html), "실제 기사 본문입니다.")

    def test_prefers_article_with_most_paragraph_text(self):
        html = """<html><body>
          <article><p>짧은 안내</p></article>
          <article><p>훨씬 더 길게 작성된 실제 기사 본문입니다.</p></article>
        </body></html>"""
        self.assertEqual(self._extract(html), "훨씬 더 길게 작성된 실제 기사 본문입니다.")

    def test_falls_back_to_whole_page_without_article_tag(self):
        html = "<html><body><div><p>문서 본문</p></div></body></html>"
        self.assertEqual(self._extract(html), "문서 본문")


class FeedSourceTests(unittest.TestCase):
    def _assert_reads_feed(self, crawler, source_name, language):
        crawler.base_url = FEED_XML
        articles = crawler.fetch()
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].source, source_name)
        self.assertEqual(articles[0].language, language)
        self.assertEqual(articles[0].published_date, date(2026, 11, 7))

    def test_autoherald_reads_feed(self):
        self._assert_reads_feed(AutoHeraldCrawler(), "오토헤럴드", "ko")

    def test_autodaily_reads_feed(self):
        self._assert_reads_feed(AutoDailyCrawler(), "오토데일리", "ko")

    def test_the_verge_reads_feed_with_dates(self):
        self._assert_reads_feed(TheVergeCrawler(), "The Verge", "en")

    def test_fleetowner_uses_live_feed_path(self):
        self.assertIn("/__rss/website-scheduled-content.xml", NEWS_SOURCES["fleetowner"])
        self.assertEqual(FleetOwnerCrawler().base_url, NEWS_SOURCES["fleetowner"])


if __name__ == "__main__":
    unittest.main()
