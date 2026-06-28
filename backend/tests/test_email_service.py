import smtplib
import uuid

import pytest

from app.models.lead import Lead, LeadState
from app.services.email import (
    EmailService,
    render_attorney_notification,
    render_prospect_confirmation,
)


def _lead():
    return Lead(
        id=uuid.uuid4(),
        first_name="Ada",
        last_name="Lovelace",
        email="ada@calc.org",
        resume_key="leads/x/resume.pdf",
        resume_filename="resume.pdf",
        state=LeadState.PENDING,
    )


class FakeSMTP:
    instances = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def send_message(self, message):
        self.sent.append(message)


def test_send_delivers_message(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    service = EmailService(host="mail.test", port=1025, email_from="no-reply@firm.test")
    service.send("to@x.org", "Subject line", "Body text")

    assert len(FakeSMTP.instances) == 1
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "mail.test"
    assert smtp.port == 1025
    assert len(smtp.sent) == 1
    message = smtp.sent[0]
    assert message["From"] == "no-reply@firm.test"
    assert message["To"] == "to@x.org"
    assert message["Subject"] == "Subject line"
    assert message.get_content().strip() == "Body text"


def test_send_swallows_errors(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(smtplib, "SMTP", boom)

    service = EmailService(host="mail.test", port=1025, email_from="no-reply@firm.test")
    service.send("to@x.org", "Subject", "Body")


def test_render_prospect_confirmation():
    subject, body = render_prospect_confirmation(_lead())
    assert "received" in subject.lower()
    assert "Ada" in body


def test_render_attorney_notification():
    subject, body = render_attorney_notification(_lead())
    assert "Ada Lovelace" in subject
    assert "ada@calc.org" in body
    assert "resume.pdf" in body
