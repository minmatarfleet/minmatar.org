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


def env_str(name, default=""):
    """Read a string from the environment; blank counts as unset."""
    value = os.environ.get(name, "").strip()
    return value if value else default


_TRUE_VALUES = {"1", "true", "yes", "on"}


def env_bool(name, default=False):
    """Read a boolean from the environment.

    Only 1/true/yes/on (any case) are true, so "False" or "0" stay false.
    Blank counts as unset.
    """
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in _TRUE_VALUES


def readonly_database_from_env():
    """The production_readonly alias, or None when it is not configured.

    Used by the *_from_production import commands and for read-only
    debugging. It is only defined when DB_READONLY_USER and
    DB_READONLY_HOST are set, so credentials live in .env, never in code.
    The session is also put in read-only mode, so a write fails even if
    the account has write grants.
    """
    user = env_str("DB_READONLY_USER")
    host = env_str("DB_READONLY_HOST")
    if not user or not host:
        return None
    return {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env_str("DB_READONLY_NAME", "minmatar"),
        "USER": user,
        "PASSWORD": env_str("DB_READONLY_PASSWORD"),
        "HOST": host,
        "PORT": env_str("DB_READONLY_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET SESSION TRANSACTION READ ONLY",
        },
    }


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

# Developer-only switches. Each one is forced off unless DEBUG is on, so a
# stray value in a production .env can never enable it. The views check
# DEBUG again at request time (app/dev_switches.py).
#
# FAKE_LOGIN_USER_ID: bypass Discord login and log in as this user ID.
FAKE_LOGIN_USER_ID = (env_str("FAKE_LOGIN_USER_ID") or None) if DEBUG else None

# Local settings only, not for production
if FAKE_LOGIN_USER_ID:
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SECURE = True
    SESSION_ENGINE = "django.contrib.sessions.backends.db"

# MOCK_ESI: serve character ESI calls from eveonline/mock_esi.
MOCK_ESI = DEBUG and env_bool("MOCK_ESI")
# SETUP_TEST_DATA: seed local test users and data on startup (app/urls.py).
SETUP_TEST_DATA = DEBUG and env_bool("SETUP_TEST_DATA")

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
