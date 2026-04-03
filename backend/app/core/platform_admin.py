"""Platform admin: DB flag and/or PLATFORM_ADMIN_EMAILS (must stay in sync with API authorization)."""

from app.core.config import settings
from app.models.user import User


def user_is_platform_admin(user: User) -> bool:
    if bool(getattr(user, "is_platform_admin", False)):
        return True
    allow = {e.strip().lower() for e in (settings.platform_admin_emails or "").split(",") if e.strip()}
    return user.email.strip().lower() in allow
