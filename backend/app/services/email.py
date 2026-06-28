from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.models.lead import Lead

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, host: str, port: int, email_from: str) -> None:
        self.host = host
        self.port = port
        self.email_from = email_from

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(self.host, self.port) as server:
                server.send_message(message)
        except Exception:
            logger.exception("Failed to send email to %s", to)


def build_email() -> EmailService:
    return EmailService(
        host=settings.smtp_host,
        port=settings.smtp_port,
        email_from=settings.email_from,
    )


def render_prospect_confirmation(lead: Lead) -> tuple[str, str]:
    subject = "We received your submission"
    body = (
        f"Hi {lead.first_name},\n\n"
        "Thanks for submitting your information. Our team has received your "
        "resume and an attorney will reach out to you shortly.\n\n"
        "Best regards,\n"
        "The Legal Team"
    )
    return subject, body


def render_attorney_notification(lead: Lead) -> tuple[str, str]:
    subject = f"New lead: {lead.first_name} {lead.last_name}"
    body = (
        "A new lead has been submitted.\n\n"
        f"Name: {lead.first_name} {lead.last_name}\n"
        f"Email: {lead.email}\n"
        f"Resume: {lead.resume_filename}\n"
        f"State: {lead.state.value}\n"
    )
    return subject, body
