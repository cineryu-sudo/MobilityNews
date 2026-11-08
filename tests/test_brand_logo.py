import unittest
from email import message_from_bytes

from bs4 import BeautifulSoup

from delivery.email_sender import EmailSender
from delivery.template import EmailTemplate
from intelligence.summarize import ArticleSummary

LOGO_SRC = "cid:lguplus-logo"


def _html():
    article = ArticleSummary(
        original_title="제목",
        translated_title="제목",
        summary="요약",
        url="https://example.com/a",
        source="오토헤럴드",
        category="자율주행",
    )
    return EmailTemplate.generate(articles=[article], executive_insight="신호")


class HeaderLogoTests(unittest.TestCase):
    def test_header_uses_official_logo_at_small_size(self):
        logo = BeautifulSoup(_html(), "html.parser").find("img", src=LOGO_SRC)
        self.assertIsNotNone(logo)
        self.assertEqual(logo["alt"], "LG U+")
        self.assertEqual((logo["width"], logo["height"]), ("63", "18"))

    def test_hand_drawn_header_logo_is_removed(self):
        soup = BeautifulSoup(_html(), "html.parser")
        hero = soup.find("td", class_="hero-pad")
        self.assertNotIn("LG U+", hero.get_text(" ", strip=True).replace("U +", "U+"))

    def test_u_plus_enterprise_mark_is_kept(self):
        self.assertIn("Enterprise", BeautifulSoup(_html(), "html.parser").get_text())


class LogoAttachmentTests(unittest.TestCase):
    def _parsed(self, html):
        message = EmailSender()._build_message(
            recipients=["a@example.com"], subject="제목", html_content=html
        )
        return message_from_bytes(message.as_bytes())

    def test_logo_is_embedded_as_inline_image(self):
        parsed = self._parsed(_html())
        images = [p for p in parsed.walk() if p.get_content_maintype() == "image"]
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["Content-ID"], "<lguplus-logo>")
        self.assertTrue(images[0].get_payload(decode=True).startswith(b"\x89PNG"))
        self.assertEqual(parsed.get_content_type(), "multipart/related")

    def test_mail_without_logo_has_no_image_part(self):
        parsed = self._parsed("<p>본문</p>")
        images = [p for p in parsed.walk() if p.get_content_maintype() == "image"]
        self.assertEqual(images, [])


if __name__ == "__main__":
    unittest.main()
