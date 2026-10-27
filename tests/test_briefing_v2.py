import unittest
from unittest.mock import patch

from crawlers.base import Article
from delivery.template import EmailTemplate
from intelligence.filter import ArticleFilter, score_team_relevance
from intelligence.organization import (
    AI_INFO_TEAM,
    CONNECTED_CAR_TEAM,
    FMS_SOLUTION_TEAM,
)
from intelligence.summarize import ArticleSummary, BriefingResult, Summarizer
from ops.qa import evaluate_briefing


class _FakeTextBlock:
    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    def __init__(self, text):
        self.text = text

    def create(self, **_kwargs):
        return _FakeResponse(self.text)


class _FakeClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


def _article(title, url="https://example.com/article", language="ko"):
    return Article(
        title=title,
        url=url,
        source="Test Source",
        language=language,
    )


def _complete_summary(**overrides):
    values = {
        "original_title": "커넥티드카와 차량관제 플랫폼 통합",
        "translated_title": "커넥티드카와 차량관제 플랫폼 통합",
        "summary": (
            "완성차가 통합 플랫폼을 공개했다. DCM 데이터 활용 범위를 확대한다. "
            "차량 운영 서비스와 연계할 계획이다."
        ),
        "url": "https://example.com/article",
        "source": "Test Source",
        "category": "커넥티드카",
        "key_points": [
            "완성차가 커넥티드카와 차량관제를 연결하는 통합 플랫폼을 공개했다.",
            "DCM에서 수집한 차량 데이터를 실시간 운영 서비스에 활용한다.",
            "플랫폼 적용 대상을 상용차와 물류 차량으로 확대할 계획이다.",
        ],
        "why_it_matters": "차량 연결 데이터가 단순 통신을 넘어 운영 서비스의 핵심 자산으로 이동하고 있다.",
        "related_teams": [CONNECTED_CAR_TEAM, FMS_SOLUTION_TEAM],
        "watch_point": "실제 상용차 고객 적용 범위와 데이터 제공 조건을 확인해야 한다.",
    }
    values.update(overrides)
    return ArticleSummary(**values)


class SummarizerV2Tests(unittest.TestCase):
    def test_generates_structured_business_brief(self):
        response_text = """
[EXECUTIVE_INSIGHT]
차량 데이터가 연결·경험·운영 사업을 잇는 공통 자산으로 확대되고 있다.

[ARTICLE_1_CATEGORY]
커넥티드카

[ARTICLE_1_RELATED_TEAMS]
커넥티드카사업팀, AI인포사업팀, FMS솔루션사업팀

[ARTICLE_1_KEY_POINTS]
- 완성차가 통합 차량 데이터 플랫폼을 공개했다.
- DCM과 인포테인먼트 데이터를 함께 활용한다.
- 차량관제 서비스로 적용 범위를 확대할 계획이다.

[ARTICLE_1_WHY_IT_MATTERS]
차량 데이터의 활용 범위가 연결 기능에서 고객 경험과 운영 최적화로 확대되고 있다.

[ARTICLE_1_WATCH_POINT]
완성차의 외부 파트너 데이터 개방 범위를 확인해야 한다.
"""
        summarizer = Summarizer.__new__(Summarizer)
        summarizer.client = _FakeClient(response_text)

        article = _article("통합 차량 데이터 플랫폼 공개")
        result = summarizer.generate_briefing([article], {})
        summary = result.articles[0]

        self.assertEqual(len(summary.key_points), 3)
        self.assertEqual(
            summary.related_teams,
            [CONNECTED_CAR_TEAM, AI_INFO_TEAM, FMS_SOLUTION_TEAM],
        )
        self.assertTrue(summary.is_cross_team_signal)
        self.assertEqual(summary.business_implication, "")


class OrganizationSelectionTests(unittest.TestCase):
    def test_scores_each_business_team_without_fixed_hierarchy(self):
        connected = _article("Automaker expands connected car DCM and OTA platform")
        infotainment = _article("New in-car OS adds digital cockpit and voice assistant")
        fleet = _article("Fleet management adopts RTK precise positioning")

        self.assertGreater(score_team_relevance(connected)[CONNECTED_CAR_TEAM], 0)
        self.assertGreater(score_team_relevance(infotainment)[AI_INFO_TEAM], 0)
        self.assertGreater(score_team_relevance(fleet)[FMS_SOLUTION_TEAM], 0)

    def test_short_keyword_does_not_match_inside_unrelated_word(self):
        article = _article("Telecom carrier reports subscriber growth")
        article_filter = ArticleFilter.__new__(ArticleFilter)

        self.assertEqual(article_filter._classify_priority(article), (0, 0))

    def test_balanced_fallback_covers_three_teams(self):
        candidates = [
            _article("Connected car DCM OTA platform", "https://example.com/connected"),
            _article("Digital cockpit infotainment OS", "https://example.com/ai-info"),
            _article("Fleet management RTK precise positioning", "https://example.com/fms"),
            _article("Electric vehicle battery market update", "https://example.com/ev"),
        ]
        article_filter = ArticleFilter.__new__(ArticleFilter)

        selected = article_filter._select_fallback_generic(candidates, 3)
        covered = {
            team
            for article in selected
            for team, score in score_team_relevance(article).items()
            if score > 0
        }

        self.assertEqual(covered, {CONNECTED_CAR_TEAM, AI_INFO_TEAM, FMS_SOLUTION_TEAM})

    def test_semantic_dedupe_removes_cross_language_duplicate(self):
        articles = [
            _article(
                "포드, 차세대 전기차에 애플 지도 기본 탑재",
                "https://example.com/korean",
            ),
            _article(
                "Ford picks Apple Maps for its next EV platform",
                "https://example.com/english",
                language="en",
            ),
            _article(
                "Fleet management adopts RTK positioning",
                "https://example.com/fleet",
                language="en",
            ),
        ]
        article_filter = ArticleFilter.__new__(ArticleFilter)
        article_filter.client = _FakeClient(
            '중복 판단 결과입니다.\n```json\n{"duplicate_indices": [2]}\n```'
        )

        selected = article_filter._remove_semantic_duplicates(articles)

        self.assertEqual(
            [article.url for article in selected],
            ["https://example.com/korean", "https://example.com/fleet"],
        )

    def test_language_quota_is_refilled_after_duplicate_removal(self):
        selected = [
            _article("국내 기사 1", "https://example.com/ko-1"),
            _article("국내 기사 2", "https://example.com/ko-2"),
            _article("국내 기사 3", "https://example.com/ko-3"),
            _article(
                "International fleet management story",
                "https://example.com/en-1",
                language="en",
            ),
        ]
        replacement = _article(
            "Connected car platform expands overseas",
            "https://example.com/en-2",
            language="en",
        )
        article_filter = ArticleFilter.__new__(ArticleFilter)

        result = article_filter._supplement_language_quotas(
            selected,
            selected + [replacement],
            exclude=selected,
        )

        self.assertEqual(sum(article.language == "ko" for article in result), 3)
        self.assertEqual(sum(article.language == "en" for article in result), 2)


class BriefingQaV2Tests(unittest.TestCase):
    def test_complete_structured_brief_passes(self):
        article = _article("커넥티드카와 차량관제 플랫폼 통합")
        briefing = BriefingResult(
            executive_insight="차량 데이터가 연결과 운영 서비스를 잇는 핵심 사업 자산으로 확대되고 있다.",
            articles=[_complete_summary()],
        )

        with patch("ops.qa.QA_MIN_ARTICLE_COUNT", 1):
            result = evaluate_briefing([article], briefing)

        self.assertTrue(result.passed)
        self.assertFalse(result.blocked)

    def test_missing_structured_fields_blocks_delivery(self):
        article = _article("차량 데이터 플랫폼 공개")
        briefing = BriefingResult(
            executive_insight="차량 데이터가 모빌리티 사업 전반의 경쟁 기반으로 확대되고 있다.",
            articles=[
                _complete_summary(
                    key_points=["한 개뿐인 핵심 포인트"],
                    why_it_matters="",
                    related_teams=[],
                )
            ],
        )

        with patch("ops.qa.QA_MIN_ARTICLE_COUNT", 1):
            result = evaluate_briefing([article], briefing)

        finding_codes = {finding.code for finding in result.findings}
        self.assertTrue(result.blocked)
        self.assertIn("invalid_key_point_count", finding_codes)
        self.assertIn("missing_why_it_matters", finding_codes)
        self.assertIn("missing_related_teams", finding_codes)


class EmailTemplateV2Tests(unittest.TestCase):
    def test_renders_integrated_business_radar_and_escapes_content(self):
        summary = _complete_summary(
            translated_title="<script>차량 데이터 플랫폼</script>",
        )

        html = EmailTemplate.generate(
            executive_insight="세 조직의 데이터 역량을 연결하는 사업 기회가 확대되고 있다.",
            articles=[summary],
        )

        self.assertIn("Mobility Business Radar", html)
        self.assertIn("Mobility Insight", html)
        self.assertIn("U<sup", html)
        self.assertIn("FOCUS STORY", html)
        self.assertIn("INSIGHT TOPICS", html)
        self.assertIn("#E6007E", html)
        self.assertNotIn("MOBILITY BUSINESS LENS", html)
        self.assertIn("CROSS-TEAM SIGNAL", html)
        self.assertIn(CONNECTED_CAR_TEAM, html)
        self.assertIn(FMS_SOLUTION_TEAM, html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
