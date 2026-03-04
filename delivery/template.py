"""
HTML email template for the daily mobility briefing.
Outlook-compatible version using table-based layout and MSO conditional code.
"""

from datetime import datetime
from typing import List

from intelligence.summarize import ArticleSummary

# Category badge colors
CATEGORY_COLORS = {
    "전기차": "#3b82f6",
    "자율주행": "#8b5cf6",
    "MaaS": "#ec4899",
    "배터리": "#14b8a6",
    "플랫폼": "#f97316",
    "커넥티드카": "#06b6d4",
    "수소차": "#10b981",
    "충전인프라": "#eab308",
    "정책/규제": "#ef4444",
    "기타": "#6b7280",
}


class EmailTemplate:
    """Generates HTML email content for the mobility briefing."""

    @staticmethod
    def _get_category_color(category: str) -> str:
        """Get badge color for a category."""
        return CATEGORY_COLORS.get(category, "#6b7280")

    @staticmethod
    def generate(
        executive_insight: str,
        articles: List[ArticleSummary],
        date: datetime = None
    ) -> str:
        """Generate Outlook-compatible HTML email content."""
        if date is None:
            date = datetime.now()

        date_str = date.strftime("%Y년 %m월 %d일")

        # Generate article rows
        article_rows = ""
        for i, article in enumerate(articles, 1):
            color = EmailTemplate._get_category_color(article.category)
            is_last = i == len(articles)
            padding_bottom = "20px" if is_last else "12px"

            article_rows += f"""
                    <!-- Article {i} -->
                    <tr>
                        <td style="padding-bottom: {padding_bottom};">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #1e293b; border-radius: 12px; border: 1px solid #334155;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td width="50" style="vertical-align: top;">
                                                    <!--[if mso]>
                                                    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color:#334155;width:36px;height:36px;text-align:center;font-size:16px;font-weight:800;color:#94a3b8;line-height:36px;">
                                                    <![endif]-->
                                                    <span style="display: inline-block; width: 36px; height: 36px; background-color: #334155; border-radius: 10px; text-align: center; line-height: 36px; font-size: 16px; font-weight: 800; color: #94a3b8;">{i}</span>
                                                    <!--[if mso]>
                                                    </td></tr></table>
                                                    <![endif]-->
                                                </td>
                                                <td style="padding-left: 14px;">
                                                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                                        <tr>
                                                            <td>
                                                                <!--[if mso]>
                                                                <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color:{color};color:#ffffff;padding:2px 8px;font-size:10px;font-weight:600;">
                                                                <![endif]-->
                                                                <span style="display: inline-block; background-color: {color}; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600;">{article.category}</span>
                                                                <!--[if mso]>
                                                                </td></tr></table>
                                                                <![endif]-->
                                                            </td>
                                                            <td style="text-align: right;">
                                                                <span style="color: #64748b; font-size: 11px;">{article.source}</span>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                    <h3 style="margin: 6px 0 8px 0; font-size: 15px; color: #f1f5f9; font-weight: 600; line-height: 1.4;">
                                                        <a href="{article.url}" style="color: #f1f5f9; text-decoration: none;">{article.translated_title}</a>
                                                    </h3>
                                                    <p style="margin: 0 0 10px 0; color: #94a3b8; font-size: 13px; line-height: 1.6;">{article.summary}</p>
                                                    <a href="{article.url}" style="color: #818cf8; font-size: 12px; text-decoration: none; font-weight: 500;">자세히 보기 &#8594;</a>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="ko" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!--[if mso]>
    <noscript>
    <xml>
    <o:OfficeDocumentSettings>
      <o:AllowPNG/>
      <o:PixelsPerInch>96</o:PixelsPerInch>
    </o:OfficeDocumentSettings>
    </xml>
    </noscript>
    <style>
        table {{ border-collapse: collapse; }}
        td {{ font-family: 'Segoe UI', Arial, sans-serif; }}
    </style>
    <![endif]-->
    <title>Mobility Daily Briefing</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0f172a; font-family: 'Segoe UI', Roboto, Arial, sans-serif; -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%;">

    <!-- Outer wrapper table for Outlook centering -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #0f172a;">
        <tr>
            <td align="center" style="padding: 20px 0;">

                <!-- Main container -->
                <table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="max-width: 640px; width: 100%;">

                    <!-- Header -->
                    <tr>
                        <td style="padding-bottom: 20px;">
                            <!--[if mso]>
                            <v:rect xmlns:v="urn:schemas-microsoft-com:vml" fill="true" stroke="false" style="width:640px;height:110px;">
                            <v:fill type="gradient" color="#6366f1" color2="#a855f7" angle="135"/>
                            <v:textbox inset="32px,28px,32px,28px" style="mso-fit-shape-to-text:false;">
                            <![endif]-->
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #7c3aed; border-radius: 16px; background-image: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);">
                                <tr>
                                    <td style="padding: 32px;">
                                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td>
                                                    <p style="margin: 0 0 4px 0; color: #d4d4d8; font-size: 12px; font-weight: 500;">LG U+ Mobility</p>
                                                    <h1 style="margin: 0 0 4px 0; color: #ffffff; font-size: 26px; font-weight: 800;">Daily Briefing</h1>
                                                    <p style="margin: 0; color: #c4b5fd; font-size: 13px;">{date_str}</p>
                                                </td>
                                                <td width="60" style="text-align: right; vertical-align: middle;">
                                                    <span style="font-size: 48px;">&#128663;</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                            <!--[if mso]>
                            </v:textbox>
                            </v:rect>
                            <![endif]-->
                        </td>
                    </tr>

                    <!-- Executive Insight -->
                    <tr>
                        <td style="padding-bottom: 20px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #1e293b; border-radius: 12px; border: 1px solid #475569;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td width="44" style="vertical-align: top;">
                                                    <!--[if mso]>
                                                    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color:#f59e0b;width:32px;height:32px;text-align:center;font-size:16px;line-height:32px;">
                                                    <![endif]-->
                                                    <span style="display: inline-block; width: 32px; height: 32px; background-color: #f59e0b; border-radius: 8px; text-align: center; line-height: 32px; font-size: 16px;">&#128161;</span>
                                                    <!--[if mso]>
                                                    </td></tr></table>
                                                    <![endif]-->
                                                </td>
                                                <td style="padding-left: 12px;">
                                                    <p style="margin: 0 0 8px 0; color: #fbbf24; font-size: 12px; font-weight: 700;">TODAY'S INSIGHT</p>
                                                    <p style="margin: 0; color: #e2e8f0; font-size: 15px; line-height: 1.7;">
                                                        {executive_insight}
                                                    </p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Section Label -->
                    <tr>
                        <td style="padding: 0 0 12px 4px;">
                            <p style="margin: 0; color: #94a3b8; font-size: 12px; font-weight: 600;">TOP {len(articles)} STORIES</p>
                        </td>
                    </tr>

                    {article_rows}

                    <!-- Footer -->
                    <tr>
                        <td style="text-align: center; padding: 20px; color: #64748b; font-size: 11px;">
                            <p style="margin: 0 0 6px 0;">AI로 자동 생성된 브리핑입니다. 개선 요청사항은 유호승(goodnews@lguplus.co.kr)에게 요청 바랍니다.</p>
                            <p style="margin: 0;">&copy; 2026 모빌리티사업TF 커넥티드카사업팀</p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>

</body>
</html>"""

        return html
