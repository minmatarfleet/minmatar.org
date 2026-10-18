"""Developer-only switches, checked at request time.

app/settings_env.py already forces these off unless DEBUG is on. They are
checked against DEBUG again here, so a setting changed some other way
(a local settings.py, override_settings) still cannot enable a fake login
or mocked ESI on a server running with DEBUG off.
"""

from django.conf import settings


def fake_login_user_id() -> str | None:
    """The user ID to log in as without Discord, or None when disabled."""
    if not settings.DEBUG:
        return None
    value = getattr(settings, "FAKE_LOGIN_USER_ID", None)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def mock_esi_enabled() -> bool:
    """True when character ESI calls should be served by the mock."""
    return bool(settings.DEBUG and getattr(settings, "MOCK_ESI", False))
