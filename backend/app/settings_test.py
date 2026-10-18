"""
Django settings for test suite.
This file is used specifically for running tests.

Env-driven settings shared with production live in app/settings_env.py;
this file overrides secrets, URLs, the database and the cache.
"""

import os

from app.monitoring import init_sentry

from app.settings_celery import *  # noqa # pylint: disable=wildcard-import
from app.settings_common import *  # noqa # pylint: disable=wildcard-import
from app.settings_env import *  # noqa # pylint: disable=wildcard-import
from app.settings_env import BASE_DIR, ENV, WEB_LINK_URL

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", "testing")
SHARED_SECRET = os.environ.get("SHARED_SECRET", "nothing")

TESTING = True

# Developer switches are always off in tests, whatever .env says. A truthy
# SETUP_TEST_DATA would seed rows at URLconf import and collide with fixtures.
FAKE_LOGIN_USER_ID = None
MOCK_ESI = False
SETUP_TEST_DATA = False
# Django's defaults, in case settings_env switched them for a fake login.
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = False
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Run Celery tasks inline in tests — no Redis broker or worker required.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CORS_ALLOWED_ORIGINS = [
    WEB_LINK_URL.rstrip("/"),
    "http://localhost:4321",
    "https://my.minmatar.org",
    "https://minmatar.org",
]

# DISCORD — never use real bot/OAuth secrets from the environment in unit tests.
# Pipenv may load a .env with production tokens; those must not reach DiscordClient.
DISCORD_BOT_TOKEN = ""
DISCORD_CLIENT_ID = ""
DISCORD_CLIENT_SECRET = ""
DISCORD_REDIRECT_URL = ""
DISCORD_ADMIN_REDIRECT_URL = ""
DISCORD_EXTERNAL_GUILD_REDIRECT_URL = (
    "http://localhost:4321/redirects/external_guild_callback"
)
DISCORD_HOLY_RAT_WEBHOOK_MINMATAR_FLEET = ""
DISCORD_HOLY_RAT_WEBHOOK_RAT_CAVE = ""
# Non-production placeholder; live verify must use app.settings + test guild.
DISCORD_GUILD_ID = 1
ALLOW_LIVE_DISCORD_IN_TESTS = False
# Never hit esi.evetech.net from the unit suite unless a test opts in.
ALLOW_LIVE_ESI_IN_TESTS = False

# ESI
ESI_CONNECTION_ERROR_MAX_RETRIES = 0  # 0 means no retries
ESI_SERVER_ERROR_MAX_RETRIES = 0  # 0 means no retries

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-unique-snowflake",
    }
}

# Always use SQLite for tests - no database permissions needed
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
        # In-memory by default. CI points this at a file so the migrated
        # schema can be cached between runs with --keepdb.
        "TEST": {"NAME": os.environ.get("TEST_DB_NAME") or None},
    }
}

# Monitoring: same setup as production, with the DSN taken only from
# the environment (empty in CI, so nothing is sent).
init_sentry(
    component="web",
    dsn=os.environ.get("SENTRY_BACKEND_DSN", ""),
    environment=os.environ.get("ENV", ENV),
)

REDDIT_REDIRECT_URL = os.environ.get(
    "REDDIT_REDIRECT_URL", "http://testserver/api/reddit/callback"
)

TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID", "test-twitch-client")
TWITCH_CLIENT_SECRET = os.environ.get(
    "TWITCH_CLIENT_SECRET", "test-twitch-secret"
)
TWITCH_REDIRECT_URL = os.environ.get(
    "TWITCH_REDIRECT_URL", "http://testserver/api/creators/twitch/callback"
)
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "test-youtube-client")
YOUTUBE_CLIENT_SECRET = os.environ.get(
    "YOUTUBE_CLIENT_SECRET", "test-youtube-secret"
)
YOUTUBE_REDIRECT_URL = os.environ.get(
    "YOUTUBE_REDIRECT_URL", "http://testserver/api/creators/youtube/callback"
)

# Unit tests must never touch the network — see app/test_network_guard.py.
if os.environ.get("ALLOW_NETWORK_IN_TESTS", "") != "True":
    from app.test_network_guard import install as _block_network

    _block_network()
