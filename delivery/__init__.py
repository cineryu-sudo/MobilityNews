"""
Delivery module for email sending.
"""

from .template import EmailTemplate
from .email_sender import EmailSender

__all__ = [
    "EmailTemplate",
    "EmailSender",
]
