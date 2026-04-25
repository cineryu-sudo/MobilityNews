"""
Gmail SMTP email sender.
"""

import smtplib
import logging
import time
from html import escape
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List

from config import (
    DELIVERY_BATCH_SIZE,
    DELIVERY_MAX_RETRIES,
    DELIVERY_RETRY_DELAY_SECONDS,
    GMAIL_ADDRESS,
    GMAIL_APP_PASSWORD,
    RECIPIENT_EMAILS,
    SMTP_TIMEOUT_SECONDS,
)
from ops.models import DeliveryBatchResult, DeliveryResult

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends HTML emails via Gmail SMTP."""
    
    def __init__(self):
        self.sender_email = GMAIL_ADDRESS
        self.app_password = GMAIL_APP_PASSWORD
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.smtp_timeout = SMTP_TIMEOUT_SECONDS
        self.batch_size = DELIVERY_BATCH_SIZE
        self.max_retries = DELIVERY_MAX_RETRIES
        self.retry_delay_seconds = DELIVERY_RETRY_DELAY_SECONDS

    @staticmethod
    def build_subject(subject: str | None = None) -> str:
        """Build the default daily subject when one is not provided."""
        if subject:
            return subject
        date_str = datetime.now().strftime("%m/%d")
        return f"[Mobility Briefing] {date_str} 모빌리티 데일리 브리핑"

    def _build_message(
        self,
        recipients: List[str],
        subject: str,
        html_content: str | None = None,
        text_content: str | None = None,
    ) -> MIMEMultipart:
        """Build an email message for one recipient batch."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Mobility Insight Bot <{self.sender_email}>"
        msg["To"] = self.sender_email
        msg["Bcc"] = ", ".join(recipients)

        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
        if html_content:
            msg.attach(MIMEText(html_content, "html", "utf-8"))
        return msg

    def _send_message(
        self,
        recipients: List[str],
        subject: str,
        html_content: str | None = None,
        text_content: str | None = None,
    ) -> DeliveryResult:
        """Send a prepared message body to recipients."""
        if recipients is None:
            recipients = RECIPIENT_EMAILS
        else:
            recipients = list(recipients)

        recipients = list(dict.fromkeys(recipients))

        if not text_content and not html_content:
            return DeliveryResult(
                success=False,
                subject=subject,
                total_recipients=len(recipients),
                error_message="No email content specified",
            )

        if not recipients:
            logger.error("No recipients specified")
            return DeliveryResult(
                success=False,
                subject=subject,
                total_recipients=0,
                error_message="No recipients specified",
            )
        
        if not self.sender_email or not self.app_password:
            logger.error("Gmail credentials not configured")
            return DeliveryResult(
                success=False,
                subject=subject,
                total_recipients=len(recipients),
                error_message="Gmail credentials not configured",
            )
        
        batch_results: List[DeliveryBatchResult] = []
        total_batches = (len(recipients) + self.batch_size - 1) // self.batch_size

        try:
            for batch_index, start in enumerate(range(0, len(recipients), self.batch_size), start=1):
                batch = recipients[start:start + self.batch_size]
                msg = self._build_message(
                    batch,
                    subject,
                    html_content=html_content,
                    text_content=text_content,
                )

                success = False
                error_message = ""
                attempts = 0
                for attempt in range(1, self.max_retries + 2):
                    attempts = attempt
                    try:
                        with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.smtp_timeout) as server:
                            server.ehlo()
                            server.starttls()
                            server.ehlo()
                            server.login(self.sender_email, self.app_password)
                            server.sendmail(self.sender_email, batch, msg.as_string())
                        success = True
                        logger.info(
                            f"Email batch {batch_index}/{total_batches} sent successfully "
                            f"({len(batch)} recipients)"
                        )
                        break
                    except smtplib.SMTPException as error:
                        error_message = str(error)
                        logger.warning(
                            f"Email batch {batch_index}/{total_batches} failed on attempt "
                            f"{attempt}/{self.max_retries + 1}: {error}"
                        )
                    except Exception as error:
                        error_message = str(error)
                        logger.warning(
                            f"Email batch {batch_index}/{total_batches} unexpected failure on "
                            f"attempt {attempt}/{self.max_retries + 1}: {error}"
                        )

                    if attempt <= self.max_retries:
                        time.sleep(self.retry_delay_seconds)

                batch_results.append(
                    DeliveryBatchResult(
                        batch_index=batch_index,
                        total_batches=total_batches,
                        recipients=batch,
                        success=success,
                        attempts=attempts,
                        error_message=error_message,
                    )
                )

                if not success:
                    logger.error(
                        f"Email batch {batch_index}/{total_batches} failed permanently "
                        f"after {attempts} attempts"
                    )
                    return DeliveryResult(
                        success=False,
                        subject=subject,
                        total_recipients=len(recipients),
                        batch_results=batch_results,
                        error_message=error_message or "Unknown delivery error",
                    )
            
            logger.info(f"Email sent successfully to {len(recipients)} recipients")
            return DeliveryResult(
                success=True,
                subject=subject,
                total_recipients=len(recipients),
                batch_results=batch_results,
            )
            
        except smtplib.SMTPAuthenticationError:
            logger.error("Gmail authentication failed. Check App Password.")
            return DeliveryResult(
                success=False,
                subject=subject,
                total_recipients=len(recipients),
                batch_results=batch_results,
                error_message="Gmail authentication failed",
            )
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return DeliveryResult(
                success=False,
                subject=subject,
                total_recipients=len(recipients),
                batch_results=batch_results,
                error_message=str(e),
            )
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return DeliveryResult(
                success=False,
                subject=subject,
                total_recipients=len(recipients),
                batch_results=batch_results,
                error_message=str(e),
            )

    def send(
        self,
        html_content: str,
        recipients: List[str] = None,
        subject: str = None
    ) -> DeliveryResult:
        """
        Send HTML email to recipients.
        """
        subject = self.build_subject(subject)
        return self._send_message(
            recipients=recipients,
            subject=subject,
            html_content=html_content,
        )

    def send_text_report(
        self,
        report_text: str,
        recipients: List[str] = None,
        subject: str = None,
    ) -> DeliveryResult:
        """Send a plain-text ops report with a simple HTML fallback."""
        text_content = report_text.strip()
        html_content = f"<html><body><pre>{escape(text_content)}</pre></body></html>"
        subject = subject or "[MobilityNews Ops Report]"
        return self._send_message(
            recipients=recipients,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )
