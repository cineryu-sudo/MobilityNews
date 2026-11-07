import unittest
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from delivery.email_sender import EmailSender
from delivery.template import EmailTemplate
from intelligence.summarize import ArticleSummary

SUBJECT = "[MobilityNews] 수신 거부 요청"


def _assert_mailto(test, url):
    parts = urlsplit(url)
    test.assertEqual(parts.scheme, "mailto")
    test.assertEqual(parts.path, "goodnews@lguplus.co.kr")
    test.assertEqual(parse_qs(parts.query)["subject"], [SUBJECT])


class UnsubscribeFooterTests(unittest.TestCase):
    def _html(self):
        article = ArticleSummary(
            original_title="제목",
            translated_title="제목",
            summary="요약",
            url="https://example.com/a",
            source="오토헤럴드",
            category="자율주행",
        )
        return EmailTemplate.generate(articles=[article], executive_insight="신호")

    def test_footer_links_to_prefilled_unsubscribe_mail(self):
        soup = BeautifulSoup(self._html(), "html.parser")
        link = soup.find("a", string="수신 거부")
        self.assertIsNotNone(link)
        _assert_mailto(self, link["href"])

    def test_footer_shows_address_for_clients_without_mailto(self):
        text = BeautifulSoup(self._html(), "html.parser").get_text(" ")
        self.assertIn(f"제목을 '{SUBJECT}'", text)
        self.assertIn("goodnews@lguplus.co.kr", text)


class ListUnsubscribeHeaderTests(unittest.TestCase):
    def test_header_contains_ascii_mailto(self):
        message = EmailSender()._build_message(
            recipients=["a@example.com"],
            subject="제목",
            html_content="<p>본문</p>",
            list_unsubscribe=True,
        )
        header = message["List-Unsubscribe"]
        self.assertTrue(header.isascii())
        _assert_mailto(self, header.strip("<>"))

    def test_ops_mail_has_no_list_unsubscribe_header(self):
        message = EmailSender()._build_message(
            recipients=["a@example.com"], subject="제목", text_content="운영 리포트"
        )
        self.assertIsNone(message["List-Unsubscribe"])


if __name__ == "__main__":
    unittest.main()
