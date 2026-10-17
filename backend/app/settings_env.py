"""
Environment-driven settings shared by every settings module.

``settings.py.example`` (the file the Dockerfile deploys as settings.py)
and ``settings_test.py`` both do ``from app.settings_env import *`` and
then add only what differs: secrets, databases, caches, CORS and test
overrides. Add a new env-driven setting here once instead of in each
settings file.

This module must stay free of side effects (no sentry init, no network).
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def env_int(name, default):
    """Read an int from the environment.

    Falls back to the default when the variable is unset *or* blank.
    A freshly copied .env.example leaves the Discord IDs below empty
    until you create your own Discord app, and a bare int("") would
    crash Django on startup.
    """
    value = os.environ.get(name, "").strip()
    return int(value) if value else default


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "False") == "True"

ALLOWED_HOSTS = [os.environ.get("ALLOWED_HOSTS", "*")]
SITE_URL = os.environ.get("CSRF_TRUSTED_ORIGIN", "http://localhost:8000")
CSRF_TRUSTED_ORIGINS = [
    "https://localhost:8000",
    "http://localhost:8000",
    "https://api.minmatar.org",
    "https://minmatar.org",
]
BROKER_URL = os.environ.get("BROKER_URL", "redis://localhost:6379/1")
CELERYBEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"

WEB_LINK_URL = os.environ.get("WEB_LINK_URL", "https://my.minmatar.org")

# DISCORD channel IDs
DISCORD_PEOPLE_TEAM_CHANNEL_ID = env_int(
    "DISCORD_PEOPLE_TEAM_CHANNEL_ID", 1098974756356771870
)
DISCORD_TECHNOLOGY_TEAM_CHANNEL_ID = env_int(
    "DISCORD_TECHNOLOGY_TEAM_CHANNEL_ID", 1174095095537078312
)
DISCORD_APPLICATION_CHANNEL_ID = env_int(
    "DISCORD_APPLICATION_CHANNEL_ID", 1097522187952467989
)
DISCORD_FLEET_SCHEDULE_CHANNEL_ID = env_int(
    "DISCORD_FLEET_SCHEDULE_CHANNEL_ID", 1174169403873558658
)
DISCORD_FLEET_SCHEDULE_MESSAGE_ID = env_int(
    "DISCORD_FLEET_SCHEDULE_MESSAGE_ID", 1244656126302224466
)
DISCORD_STRUCTURE_PINGS_CHANNEL_ID = env_int(
    "DISCORD_STRUCTURE_PINGS_CHANNEL_ID", 1270780039272595549
)
DISCORD_INDUSTRY_CHANNEL_ID = env_int(
    "DISCORD_INDUSTRY_CHANNEL_ID", 1062178037875081226
)
DISCORD_AARS_FORUM_CHANNEL_ID = env_int(
    "DISCORD_AARS_FORUM_CHANNEL_ID", 1069380111897481256
)

# Roam Report
ROAM_REPORT_API_KEY = os.environ.get("ROAM_REPORT_API_KEY", "")
ROAM_REPORT_API_URL = os.environ.get(
    "ROAM_REPORT_API_URL", "https://www.roamreport.com/api/fleets"
)

# ESI
ESI_SSO_CLIENT_ID = os.environ.get("ESI_SSO_CLIENT_ID", "")
ESI_SSO_CLIENT_SECRET = os.environ.get("ESI_SSO_CLIENT_SECRET", "")
ESI_SSO_CALLBACK_URL = os.environ.get("ESI_SSO_CALLBACK_URL", "")
ESI_USER_CONTACT_EMAIL = os.environ.get(
    "ESI_USER_CONTACT_EMAIL", "admin@minmatar.org"
)

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "/oauth2/login/"
LOGOUT_REDIRECT_URL = "/oauth2/login/"

STATIC_ROOT = os.path.join(
    BASE_DIR,
    "static",
)

# Monitoring
ENV = "production"  # pylint: disable=invalid-name
if DEBUG:
    ENV = "development"  # pylint: disable=invalid-name

# If this is set, Discord login will be bypassed and the user will be logged in with this ID
FAKE_LOGIN_USER_ID = os.environ.get("FAKE_LOGIN_USER_ID ", None)

# Local settings only, not for production
if FAKE_LOGIN_USER_ID:
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SECURE = True
    SESSION_ENGINE = "django.contrib.sessions.backends.db"


MOCK_ESI = os.environ.get("MOCK_ESI ", False)
SETUP_TEST_DATA = os.environ.get("SETUP_TEST_DATA", False)

REDDIT_USERNAME = os.environ.get("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.environ.get("REDDIT_PASSWORD", "")
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_SECRET = os.environ.get("REDDIT_SECRET", "")

# Notifications (web push / Discord DM / Eve mail)
NOTIFICATIONS_EVE_MAIL_CHARACTER_ID = int(
    os.environ.get("NOTIFICATIONS_EVE_MAIL_CHARACTER_ID", "634915984")
)
NOTIFICATIONS_DISCORD_DM_RATE_PER_SECOND = float(
    os.environ.get("NOTIFICATIONS_DISCORD_DM_RATE_PER_SECOND", "2")
)
NOTIFICATIONS_EVE_MAIL_RATE_PER_SECOND = float(
    os.environ.get("NOTIFICATIONS_EVE_MAIL_RATE_PER_SECOND", "0.5")
)
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CONTACT = os.environ.get("VAPID_CONTACT", "")
