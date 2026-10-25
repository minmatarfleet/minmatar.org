import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Celery beat
BROKER_URL = "redis://localhost:6379/1"  # Allianceauth uses 0
CACHE_URL = "redis://localhost:6379/2"


# ESI
# LOGIN_URL="/authentication/login"

# Application definition
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Django packages
    "django_admin_tabs",
    "django_extensions",
    "django_celery_beat",
    "app",
    "safedelete",
    "esi",
    # Discord auth
    "discord.apps.DiscordConfig",
    "eveonline.apps.EveonlineConfig",
    "groups.apps.GroupsConfig",
    "alliance.apps.AllianceConfig",
    "tribes.apps.TribesConfig",
    "applications.apps.ApplicationsConfig",
    "users.apps.UsersConfig",
    "fittings.apps.FittingsConfig",
    "structures.apps.StructuresConfig",
    "access_lists.apps.AccessListsConfig",
    "fleets.apps.FleetsConfig",
    # Reminders
    "reminders.apps.RemindersConfig",
    # Freight
    "freight.apps.FreightConfig",
    # Buyback
    "buyback.apps.BuybackConfig",
    # Posts
    "posts.apps.PostsConfig",
    # Moons
    "moons.apps.MoonsConfig",
    # Market
    "market.apps.MarketConfig",
    # Industry (type breakdown, etc.)
    "industry.apps.IndustryConfig",
    "sovereignty.apps.SovereigntyConfig",
    "eveuniverse",
    # 'colorfield',
    # "bootstrap_datepicker_plus",
    # Combat log analysis
    "combatlog",
    # SRP
    "srp",
    # Onboarding acknowledgments (per program version)
    "onboarding",
    # Generic page/section reading progress
    "page_progress",
    # Learning Center (certificates + abstract learnings)
    "learning",
    # Referral links,
    "referrals",
    # User subscriptions
    "subscriptions",
    # Multi-channel notifications (prefs + delivery)
    "notifications.apps.NotificationsConfig",
    # Audit history
    "audit",
    # Reddit integration
    "reddit",
    # Corporation recruitment threads on the EVE Online forums
    "recruitment.apps.RecruitmentConfig",
    # Creator Twitch / YouTube / Reddit OAuth + ingest
    "creators.apps.CreatorsConfig",
    "feed.apps.FeedConfig",
    "intel.apps.IntelConfig",
    "help_tickets.apps.HelpTicketsConfig",
    # Quarterly community surveys
    "surveys.apps.SurveysConfig",
    # Live multi-system Faction Warfare campaigns
    "campaigns.apps.CampaignsConfig",
    "capabilities.apps.CapabilitiesConfig",
    # Pilot timezones and the USTZ/EUTZ/AUTZ Discord roles
    "timezones.apps.TimezonesConfig",
]

# Discord Login


MIDDLEWARE = [
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static files
    "django.middleware.security.SecurityMiddleware",
    # Answer browser CORS preflight (OPTIONS) before URL routing → 405.
    "app.cors.SimpleCorsMiddleware",
    # Count which desktop versions call the API (X-Minmatar-Client).
    "app.client_versions.ClientVersionMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTHENTICATION_BACKENDS = [
    # "eve_auth.backends.EveSSOBackend",
]

ROOT_URLCONF = "app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": ["templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": CACHE_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "loggers": {
        "": {
            "level": "INFO",
            "handlers": ["console"],
        },
        "celery": {
            "level": "WARNING",
            "handlers": ["console"],
        },
        "celery.task": {
            "level": "WARNING",
            "handlers": ["console"],
        },
    },
}

# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# EVE Universe Settings
EVEUNIVERSE_LOAD_DOGMAS = True

# ESI token management settings
ESI_ALWAYS_CREATE_TOKEN = True

# Janice (https://janice.e-351.com) - optional; get key from kukki#3914 on Discord
JANICE_API_KEY = ""
JANICE_API_URL = "https://janice.e-351.com/api/rest/v2/pricer"

# Which answer the site gates pages on: "legacy" (Django permission strings),
# "shadow" (legacy, but report where pilot features disagree), or "features".
# Read by GET /api/users/me/gates; change it and restart the app to flip.
FRONTEND_GATE_SOURCE = os.environ.get("FRONTEND_GATE_SOURCE", "legacy")

# Optional integrations, read directly as settings.X. Empty means "not
# configured". They live here so every settings file, including local
# copies of settings.py, defines them.
#
# Base URL of the Django admin; when set, doctrine/fitting change DMs link
# to the review queues there.
MINMATAR_ADMIN_BASE_URL = os.environ.get("MINMATAR_ADMIN_BASE_URL", "")
# Bot invite link shown to corporations; defaults to one built from
# DISCORD_CLIENT_ID.
DISCORD_BOT_INVITE_URL = os.environ.get("DISCORD_BOT_INVITE_URL", "")
# Where Discord sends a CEO or director back after adding the bot to their
# corporation's server: <api>/api/eveonline/corporations/corporations/
# discord/bot/callback, also listed under OAuth2 > Redirects in the Discord
# application. Empty hides "Add our bot" on the corporation Settings tab.
DISCORD_CORP_BOT_REDIRECT_URL = os.environ.get(
    "DISCORD_CORP_BOT_REDIRECT_URL", ""
)
# SDE sqlite for campaign area names; defaults to the newest
# frontend/app/src/data/sde-*.sqlite.
EVE_SDE_SQLITE_PATH = os.environ.get("EVE_SDE_SQLITE_PATH", "")

# Reverse proxies in front of the app that each append the address they saw
# to X-Forwarded-For. Production runs one nginx hop (proxy/); set this to 0
# if the app is reached directly, or add one per extra hop (e.g. a CDN).
# EDGE_PROXY_HOPS is set by docker-compose-prod.yml for the edge proxy that
# sits behind those (docs/architecture/deploys.md), so .env needn't change.
TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "1")) + int(
    os.environ.get("EDGE_PROXY_HOPS", "0")
)

# The daily alliance health snapshot prune deletes rows (older than 35 days,
# down to one per day), so it only runs when this is turned on. Off by
# default: no snapshot history is deleted without sign-off.
ALLIANCE_HEALTH_SNAPSHOT_PRUNE_ENABLED = os.environ.get(
    "ALLIANCE_HEALTH_SNAPSHOT_PRUNE_ENABLED", ""
).strip().lower() in {"1", "true", "yes", "on"}
