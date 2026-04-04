from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx

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


def _sendgrid_configured() -> bool:
    return bool((settings.sendgrid_api_key or "").strip() and settings.smtp_from_email)


def _send_via_sendgrid(*, to_email: str, subject: str, body: str) -> bool:
    """SendGrid v3 Mail Send (plain text)."""
    payload: dict[str, Any] = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": settings.smtp_from_email},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        r = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {settings.sendgrid_api_key.strip()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15.0,
        )
        if r.status_code >= 400:
            logger.error(
                "SendGrid error for %s: status=%s body=%s",
                to_email,
                r.status_code,
                (r.text or "")[:500],
            )
            return False
        return True
    except Exception as e:
        logger.exception("SendGrid request failed for %s: %s", to_email, e)
        return False


def send_email(*, to_email: str, subject: str, body: str) -> bool:
    if settings.email_capture_mode:
        _captured.append({"to": to_email, "subject": subject, "body": body})
        logger.debug("email_capture_mode: stored message to %s", to_email)
        return True
    if _sendgrid_configured():
        return _send_via_sendgrid(to_email=to_email, subject=subject, body=body)
    if not _smtp_configured():
        logger.info("Email not configured (no SendGrid key / SMTP); skipping email to %s", to_email)
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
    except Exception as e:
        logger.exception("Failed to send email to %s: %s", to_email, e)
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


def send_workspace_invite_email(
    *,
    to_email: str,
    token: str,
    workspace_name: str,
    role_name: str,
) -> bool:
    link = f"{settings.app_base_url.rstrip('/')}/invite/{token}"
    return send_email(
        to_email=to_email,
        subject=f"Invitation to {workspace_name} on Enterprise Copilot",
        body=(
            f"You have been invited to workspace \"{workspace_name}\" as {role_name}.\n\n"
            f"Accept the invitation: {link}\n"
        ),
    )
