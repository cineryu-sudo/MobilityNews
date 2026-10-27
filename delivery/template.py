"""
LG U+ Enterprise-inspired HTML template for the Mobility Business Radar.
"""

from datetime import datetime
from html import escape
from typing import List

from intelligence.organization import (
    AI_INFO_TEAM,
    COMMON_TEAM,
    CONNECTED_CAR_TEAM,
    FMS_SOLUTION_TEAM,
    ORGANIZATION_TEAMS,
)
from intelligence.summarize import ArticleSummary

BI_MAGENTA = "#E6007E"
BI_MAGENTA_DARK = "#B50068"
BI_PURPLE = "#4C216D"
BI_INK = "#101014"
BI_TEXT = "#45434D"
BI_MUTED = "#77727F"
BI_LAVENDER = "#F5F2F8"
BI_BORDER = "#E6E0EA"

TEAM_STYLES = {
    CONNECTED_CAR_TEAM: ("#F1ECF7", "#4C216D"),
    AI_INFO_TEAM: ("#FCE8F3", "#B50068"),
    FMS_SOLUTION_TEAM: ("#EBEEF9", "#34447A"),
    COMMON_TEAM: ("#F0EFF2", "#45434D"),
}

TEAM_METRIC_LABELS = {
    CONNECTED_CAR_TEAM: "CONNECTED CAR / DCM",
    AI_INFO_TEAM: "AI INFOTAINMENT",
    FMS_SOLUTION_TEAM: "LOCATION / FLEET",
}


class EmailTemplate:
    """Generate an organization-aware briefing using LG U+ BI styling."""

    @staticmethod
    def _safe(value: str) -> str:
        return escape(str(value or ""), quote=True)

    @staticmethod
    def _team_badges(article: ArticleSummary) -> str:
        badges = []
        for team in article.related_teams:
            background, foreground = TEAM_STYLES.get(team, TEAM_STYLES[COMMON_TEAM])
            badges.append(
                f'<span style="display:inline-block;margin:0 5px 5px 0;'
                f'padding:4px 8px;border-radius:3px;background-color:{background};'
                f'color:{foreground};font-size:10px;font-weight:700;">'
                f'{EmailTemplate._safe(team)}</span>'
            )
        if article.is_cross_team_signal:
            badges.append(
                f'<span style="display:inline-block;margin:0 5px 5px 0;padding:4px 8px;'
                f'border-radius:3px;background-color:{BI_PURPLE};color:#FFFFFF;'
                f'font-size:10px;font-weight:700;">CROSS-TEAM SIGNAL</span>'
            )
        return "".join(badges)

    @staticmethod
    def _key_point_rows(article: ArticleSummary, compact: bool = False) -> str:
        key_points = article.key_points or ([article.summary] if article.summary else [])
        bottom_padding = "5px" if compact else "7px"
        return "".join(
            f"""
            <tr>
                <td width="17" style="padding:0 0 {bottom_padding} 0;vertical-align:top;color:{BI_MAGENTA};font-size:15px;line-height:1.45;">&#8226;</td>
                <td style="padding:0 0 {bottom_padding} 0;color:{BI_TEXT};font-size:13px;line-height:1.58;">{EmailTemplate._safe(point)}</td>
            </tr>"""
            for point in key_points
        )

    @staticmethod
    def _watch_panel(article: ArticleSummary) -> str:
        if not article.watch_point:
            return ""
        return f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:12px;background-color:#FAF8FC;border-left:3px solid #C9B4D8;">
            <tr>
                <td style="padding:10px 12px;">
                    <span style="color:{BI_PURPLE};font-size:10px;font-weight:800;letter-spacing:0.4px;">WATCH NEXT</span>
                    <span style="color:{BI_TEXT};font-size:12px;line-height:1.55;"> &nbsp;{EmailTemplate._safe(article.watch_point)}</span>
                </td>
            </tr>
        </table>"""

    @staticmethod
    def _coverage_panel(articles: List[ArticleSummary]) -> str:
        counts = {
            team: sum(team in article.related_teams for article in articles)
            for team in ORGANIZATION_TEAMS
        }
        max_count = max(counts.values(), default=1) or 1
        rows = []
        for team in ORGANIZATION_TEAMS:
            count = counts[team]
            bar_width = max(8, round((count / max_count) * 100)) if count else 0
            _, foreground = TEAM_STYLES[team]
            rows.append(
                f"""
                <tr>
                    <td style="padding:11px 0;border-bottom:1px solid #EEE9F1;">
                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                                <td style="color:{BI_MAGENTA};font-size:9px;font-weight:800;letter-spacing:0.3px;">{TEAM_METRIC_LABELS[team]}</td>
                                <td width="38" style="text-align:right;color:{BI_INK};font-size:18px;font-weight:800;">{count}</td>
                            </tr>
                            <tr>
                                <td colspan="2" style="padding-top:7px;">
                                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                        <tr>
                                            <td style="height:4px;background-color:#EEE7F0;font-size:1px;line-height:1px;">
                                                <table role="presentation" width="{bar_width}%" cellpadding="0" cellspacing="0" border="0">
                                                    <tr><td style="height:4px;background-color:{foreground};font-size:1px;line-height:1px;">&nbsp;</td></tr>
                                                </table>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>"""
            )
        return "".join(rows)

    @staticmethod
    def _focus_story(article: ArticleSummary, articles: List[ArticleSummary]) -> str:
        safe_url = EmailTemplate._safe(article.url)
        return f"""
        <tr>
            <td class="section-pad" style="padding:30px 34px 12px 34px;background-color:#FFFFFF;">
                <p style="margin:0 0 17px 0;color:{BI_MAGENTA};font-size:11px;font-weight:800;letter-spacing:0.6px;">FOCUS STORY</p>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td class="stack-cell focus-copy" width="57%" style="padding:0 25px 0 0;vertical-align:top;">
                            <p style="margin:0 0 7px 0;color:{BI_MUTED};font-size:10px;font-weight:700;">{EmailTemplate._safe(article.category)} &nbsp;|&nbsp; {EmailTemplate._safe(article.source)}</p>
                            <h2 style="margin:0 0 12px 0;color:{BI_INK};font-family:Arial,'Apple SD Gothic Neo',sans-serif;font-size:25px;line-height:1.38;font-weight:800;">
                                {EmailTemplate._safe(article.translated_title)}
                            </h2>
                            <div style="margin-bottom:10px;">{EmailTemplate._team_badges(article)}</div>
                            <p style="margin:0 0 13px 0;color:{BI_TEXT};font-size:13px;line-height:1.65;">{EmailTemplate._safe(article.why_it_matters)}</p>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                {EmailTemplate._key_point_rows(article, compact=True)}
                            </table>
                            {EmailTemplate._watch_panel(article)}
                            <p style="margin:18px 0 0 0;">
                                <a href="{safe_url}" style="display:inline-block;padding:8px 16px;border:1px solid #A9A4AD;border-radius:18px;color:{BI_INK};font-size:11px;font-weight:700;text-decoration:none;">자세히 보기 &nbsp;&rarr;</a>
                            </p>
                        </td>
                        <td class="stack-cell focus-metrics" width="43%" style="padding:0;vertical-align:top;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#FFFFFF;border:1px solid {BI_BORDER};border-radius:10px;box-shadow:0 4px 12px rgba(41,21,54,0.08);">
                                <tr>
                                    <td style="padding:17px 18px 10px 18px;">
                                        <p style="margin:0 0 3px 0;color:{BI_PURPLE};font-size:10px;font-weight:800;letter-spacing:0.5px;">ORGANIZATION SIGNALS</p>
                                        <p style="margin:0;color:{BI_MUTED};font-size:10px;">오늘의 기사 연관도</p>
                                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:8px;">
                                            {EmailTemplate._coverage_panel(articles)}
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>"""

    @staticmethod
    def _insight_topics(articles: List[ArticleSummary]) -> str:
        rows = []
        for index, article in enumerate(articles, 2):
            safe_url = EmailTemplate._safe(article.url)
            rows.append(
                f"""
                <tr>
                    <td style="padding:0 0 14px 0;">
                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#FFFFFF;border:1px solid {BI_BORDER};border-radius:9px;">
                            <tr>
                                <td class="article-pad" style="padding:20px 22px;">
                                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                        <tr>
                                            <td style="vertical-align:top;">
                                                <p style="margin:0;color:{BI_MAGENTA};font-size:9px;font-weight:800;letter-spacing:0.5px;">INSIGHT {index:02d} &nbsp;·&nbsp; {EmailTemplate._safe(article.category)}</p>
                                            </td>
                                            <td style="text-align:right;color:{BI_MUTED};font-size:10px;">{EmailTemplate._safe(article.source)}</td>
                                        </tr>
                                    </table>
                                    <h3 style="margin:8px 0 9px 0;color:{BI_PURPLE};font-family:Arial,'Apple SD Gothic Neo',sans-serif;font-size:19px;line-height:1.45;font-weight:800;">
                                        <a href="{safe_url}" style="color:{BI_PURPLE};text-decoration:none;">{EmailTemplate._safe(article.translated_title)}</a>
                                    </h3>
                                    <div style="margin-bottom:8px;">{EmailTemplate._team_badges(article)}</div>
                                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                        {EmailTemplate._key_point_rows(article)}
                                    </table>
                                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:8px;border-top:1px solid #EEE9F1;">
                                        <tr>
                                            <td style="padding:12px 0 0 0;">
                                                <p style="margin:0 0 4px 0;color:{BI_MAGENTA};font-size:9px;font-weight:800;letter-spacing:0.5px;">WHY IT MATTERS</p>
                                                <p style="margin:0;color:{BI_TEXT};font-size:12px;line-height:1.58;">{EmailTemplate._safe(article.why_it_matters)}</p>
                                            </td>
                                        </tr>
                                    </table>
                                    {EmailTemplate._watch_panel(article)}
                                    <p style="margin:14px 0 0 0;"><a href="{safe_url}" style="color:{BI_MAGENTA};font-size:11px;font-weight:800;text-decoration:none;">원문 확인 &rarr;</a></p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>"""
            )
        return "".join(rows)

    @staticmethod
    def generate(
        executive_insight: str,
        articles: List[ArticleSummary],
        date: datetime = None,
    ) -> str:
        """Generate responsive, Outlook-compatible HTML email content."""
        date = date or datetime.now()
        date_str = date.strftime("%Y.%m.%d")
        focus_story = EmailTemplate._focus_story(articles[0], articles) if articles else ""
        insight_topics = EmailTemplate._insight_topics(articles[1:]) if len(articles) > 1 else ""

        html = f"""<!DOCTYPE html>
<html lang="ko" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mobility Business Radar</title>
    <style>
        @media only screen and (max-width: 680px) {{
            .container {{ width:100% !important; }}
            .outer-pad {{ padding:0 !important; }}
            .hero-pad {{ padding:24px 20px 28px 20px !important; }}
            .section-pad {{ padding:24px 18px 10px 18px !important; }}
            .article-pad {{ padding:18px 16px !important; }}
            .stack-cell {{ display:block !important;width:auto !important; }}
            .focus-copy {{ padding-right:0 !important;padding-bottom:20px !important; }}
        }}
    </style>
    <!--[if mso]>
    <noscript><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
    <style>table {{ border-collapse:collapse; }} td {{ font-family:Arial,sans-serif; }}</style>
    <![endif]-->
</head>
<body style="margin:0;padding:0;background-color:#ECE9F0;font-family:Arial,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#ECE9F0;">
        <tr>
            <td class="outer-pad" align="center" style="padding:22px 10px;">
                <table class="container" role="presentation" width="680" cellpadding="0" cellspacing="0" border="0" style="width:680px;max-width:680px;background-color:#FFFFFF;box-shadow:0 3px 18px rgba(38,22,48,0.12);">
                    <tr>
                        <td class="hero-pad" style="padding:24px 34px 34px 34px;background-color:{BI_LAVENDER};background-image:linear-gradient(135deg,#FFFFFF 0%,#F7F3FA 58%,#EEE7F4 100%);">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td style="vertical-align:middle;">
                                        <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td width="25" height="25" style="width:25px;height:25px;border-radius:50%;background-color:{BI_MAGENTA};text-align:center;color:#FFFFFF;font-size:8px;font-weight:800;line-height:25px;">LG</td>
                                                <td style="padding-left:7px;color:#303037;font-size:16px;font-weight:800;">LG U<sup style="font-size:9px;">+</sup></td>
                                            </tr>
                                        </table>
                                    </td>
                                    <td style="text-align:right;color:#3E3942;font-size:12px;"><span style="color:{BI_MAGENTA};font-size:18px;font-weight:800;">U<sup style="font-size:10px;">+</sup></span> Enterprise</td>
                                </tr>
                            </table>

                            <p style="margin:43px 0 4px 0;color:{BI_MAGENTA};font-size:10px;font-weight:800;letter-spacing:1.1px;">MOBILITY BUSINESS RADAR</p>
                            <h1 style="margin:0;color:#050506;font-family:Arial,'Apple SD Gothic Neo',sans-serif;font-size:43px;line-height:1.12;font-weight:900;letter-spacing:-1.5px;">Mobility Insight</h1>
                            <p style="margin:14px 0 0 0;color:#29272E;font-size:14px;font-weight:700;line-height:1.55;">도시와 사람을 연결하는 모빌리티 비즈니스 인사이트</p>
                            <p style="margin:10px 0 0 0;color:#504C56;font-size:11px;">{date_str} &nbsp;|&nbsp; Daily Brief</p>

                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:27px;">
                                <tr>
                                    <td width="9" height="9" style="width:9px;height:9px;border-radius:50%;background-color:{BI_MAGENTA};font-size:1px;line-height:1px;">&nbsp;</td>
                                    <td style="height:2px;background-color:#DDA8C9;font-size:1px;line-height:1px;">&nbsp;</td>
                                    <td width="7" height="7" style="width:7px;height:7px;border-radius:50%;background-color:#C8AED7;font-size:1px;line-height:1px;">&nbsp;</td>
                                    <td width="27%" style="height:2px;background-color:#C8AED7;font-size:1px;line-height:1px;">&nbsp;</td>
                                    <td width="9" height="9" style="width:9px;height:9px;border-radius:50%;background-color:{BI_MAGENTA};font-size:1px;line-height:1px;">&nbsp;</td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:20px 34px;background-color:#FFFFFF;border-bottom:1px solid {BI_BORDER};">
                            <p style="margin:0 0 6px 0;color:{BI_MAGENTA};font-size:10px;font-weight:800;letter-spacing:0.6px;">TODAY'S SIGNAL</p>
                            <p style="margin:0;color:{BI_INK};font-size:17px;font-weight:800;line-height:1.55;">{EmailTemplate._safe(executive_insight)}</p>
                        </td>
                    </tr>

                    {focus_story}

                    <tr>
                        <td style="padding:22px 34px 12px 34px;background-color:#FBF9FC;border-top:1px solid {BI_BORDER};">
                            <p style="margin:0;color:{BI_MAGENTA};font-size:11px;font-weight:800;letter-spacing:0.6px;">INSIGHT TOPICS</p>
                        </td>
                    </tr>
                    <tr>
                        <td class="section-pad" style="padding:0 34px 26px 34px;background-color:#FBF9FC;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                {insight_topics}
                            </table>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:20px 28px;border-top:1px solid {BI_BORDER};background-color:#FFFFFF;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td style="color:#3A3740;font-size:14px;font-weight:800;"><span style="display:inline-block;margin-right:6px;width:20px;height:20px;border-radius:50%;background-color:{BI_MAGENTA};color:#FFFFFF;text-align:center;font-size:7px;line-height:20px;">LG</span>LG U<sup style="font-size:8px;">+</sup></td>
                                    <td style="text-align:right;color:{BI_MUTED};font-size:10px;">문의: goodnews@lguplus.co.kr</td>
                                </tr>
                                <tr>
                                    <td colspan="2" style="padding-top:9px;color:#99949E;font-size:9px;line-height:1.5;">AI가 생성한 산업 브리핑입니다. 중요한 의사결정 전에는 원문을 확인해 주세요.<br>&copy; 2026 LG Uplus Corp. All rights reserved.</td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
        return html
