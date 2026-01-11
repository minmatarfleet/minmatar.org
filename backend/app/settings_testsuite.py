"""
Django settings for my.minmatar.org project.
Some Docker configs replace this with a copy of settings.py.example
"""

import os
from pathlib import Path

import sentry_sdk

from app.settings_celery import *  # noqa
from app.settings_common import *  # noqa

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", "testing")
SHARED_SECRET = os.environ.get("SHARED_SECRET", "nothing")

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

# DISCORD
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URL = os.environ.get("DISCORD_REDIRECT_URL", "")
DISCORD_ADMIN_REDIRECT_URL = os.environ.get("DISCORD_ADMIN_REDIRECT_URL", "")
DISCORD_HOLY_RAT_WEBHOOK_MINMATAR_FLEET = os.environ.get(
    "DISCORD_HOLY_RAT_WEBHOOK_MINMATAR_FLEET", ""
)
DISCORD_HOLY_RAT_WEBHOOK_RAT_CAVE = os.environ.get(
    "DISCORD_HOLY_RAT_WEBHOOK_RAT_CAVE", ""
)
DISCORD_GUILD_ID = int(os.environ.get("DISCORD_GUILD_ID", 1041384161505722368))
DISCORD_PEOPLE_TEAM_CHANNEL_ID = int(
    os.environ.get("DISCORD_PEOPLE_TEAM_CHANNEL_ID", 1098974756356771870)
)
DISCORD_TECHNOLOGY_TEAM_CHANNEL_ID = int(
    os.environ.get("DISCORD_TECHNOLOGY_TEAM_CHANNEL_ID", 1174095095537078312)
)
DISCORD_APPLICATION_CHANNEL_ID = int(
    os.environ.get("DISCORD_APPLICATION_CHANNEL_ID", 1097522187952467989)
)
DISCORD_FLEET_SCHEDULE_CHANNEL_ID = int(
    os.environ.get("DISCORD_FLEET_SCHEDULE_CHANNEL_ID", 1174169403873558658)
)
DISCORD_FLEET_SCHEDULE_MESSAGE_ID = int(
    os.environ.get("DISCORD_FLEET_SCHEDULE_MESSAGE_ID", 1244656126302224466)
)
DISCORD_STRUCTURE_PINGS_CHANNEL_ID = int(
    os.environ.get("DISCORD_STRUCTURE_PINGS_CHANNEL_ID", 1270780039272595549)
)
DISCORD_SUPPLY_CHANNEL_ID = int(
    os.environ.get("DISCORD_SUPPLY_CHANNEL_ID", 1174095138197340300)
)

# ESI
ESI_SSO_CLIENT_ID = os.environ.get("ESI_SSO_CLIENT_ID", "")
ESI_SSO_CLIENT_SECRET = os.environ.get("ESI_SSO_CLIENT_SECRET", "")
ESI_SSO_CALLBACK_URL = os.environ.get("ESI_SSO_CALLBACK_URL", "")
ESI_CONNECTION_ERROR_MAX_RETRIES = 0  # 0 means no retries
ESI_SERVER_ERROR_MAX_RETRIES = 0  # 0 means no retries
ESI_USER_CONTACT_EMAIL = os.environ.get(
    "ESI_USER_CONTACT_EMAIL", "admin@minmatar.org"
)

# MUMBLE
MUMBLE_MURMUR_HOST = os.environ.get("MUMBLE_MURMUR_HOST", "")
MUMBLE_MURMUR_PORT = os.environ.get("MUMBLE_MURMUR_PORT", "")

if SECRET_KEY == "testing":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "minmatar"),
            "USER": os.environ.get("DB_USER", "root"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "example"),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        },
    }

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
ENV = "production"
if DEBUG:
    ENV = "development"

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_BACKEND_DSN", ""),
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
    environment=os.environ.get("ENV", ENV),
    _experiments={"enable_logs": True},
)

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
