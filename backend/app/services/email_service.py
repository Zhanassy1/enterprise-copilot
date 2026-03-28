from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_captured: list[dict[str, Any]] = []


def clear_captured_emails() -> None:
    """Test helper: reset in-memory capture buffer."""
    _captured.clear()


def get_captured_emails() -> list[dict[str, Any]]:
    """Copy of emails captured when email_capture_mode is True."""
    return list(_captured)


def _smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


def send_email(*, to_email: str, subject: str, body: str) -> bool:
    if settings.email_capture_mode:
        _captured.append({"to": to_email, "subject": subject, "body": body})
        logger.debug("email_capture_mode: stored message to %s", to_email)
        return True
    if not _smtp_configured():
        logger.info("SMTP not configured; skipping email to %s with subject %s", to_email, subject)
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def send_verification_email(email: str, token: str) -> bool:
    link = f"{settings.app_base_url}/verify-email?token={token}"
    return send_email(
        to_email=email,
        subject="Verify your Enterprise Copilot account",
        body=f"Verify email by opening: {link}",
    )


def send_password_reset_email(email: str, token: str) -> bool:
    link = f"{settings.app_base_url}/reset-password?token={token}"
    return send_email(
        to_email=email,
        subject="Enterprise Copilot password reset",
        body=f"Reset password by opening: {link}",
    )
