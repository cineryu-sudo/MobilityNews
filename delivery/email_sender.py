"""
Gmail SMTP email sender.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List

from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, RECIPIENT_EMAILS

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends HTML emails via Gmail SMTP."""
    
    def __init__(self):
        self.sender_email = GMAIL_ADDRESS
        self.app_password = GMAIL_APP_PASSWORD
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
    
    def send(
        self,
        html_content: str,
        recipients: List[str] = None,
        subject: str = None
    ) -> bool:
        """
        Send HTML email to recipients.
        
        Args:
            html_content: HTML email body
            recipients: List of recipient emails (defaults to RECIPIENT_EMAILS)
            subject: Email subject (defaults to today's briefing title)
        
        Returns:
            True if sent successfully, False otherwise
        """
        if recipients is None:
            recipients = RECIPIENT_EMAILS
        
        if not recipients:
            logger.error("No recipients specified")
            return False
        
        if not self.sender_email or not self.app_password:
            logger.error("Gmail credentials not configured")
            return False
        
        if subject is None:
            date_str = datetime.now().strftime("%m/%d")
            subject = f"[Mobility Briefing] {date_str} 모빌리티 데일리 브리핑"
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"Mobility Insight Bot <{self.sender_email}>"
            msg["To"] = ", ".join(recipients)
            
            # Attach HTML content
            html_part = MIMEText(html_content, "html", "utf-8")
            msg.attach(html_part)
            
            # Send via SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, recipients, msg.as_string())
            
            logger.info(f"Email sent successfully to {len(recipients)} recipients")
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error("Gmail authentication failed. Check App Password.")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
