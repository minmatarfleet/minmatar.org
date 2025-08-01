from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Celery beat
BROKER_URL = "redis://localhost:6379/1"  # Allianceauth uses 0
CELERY_IMPORTS = (
    "eveonline.tasks",
    "structures.tasks",
    "groups.tasks",
    "discord.tasks",
    "fleets.tasks",
    "reminders.tasks",
    "moons.tasks",
    "freight.tasks",
    "market.tasks",
    "mumble.tasks",
)


# Crispy forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

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
    "django_extensions",
    "django_celery_beat",
    "esi",
    # Discord auth
    "discord.apps.DiscordConfig",
    "eveonline.apps.EveonlineConfig",
    "groups.apps.GroupsConfig",
    "applications.apps.ApplicationsConfig",
    "users.apps.UsersConfig",
    "fittings.apps.FittingsConfig",
    "structures.apps.StructuresConfig",
    "fleets.apps.FleetsConfig",
    # Mumble
    "mumble.apps.MumbleConfig",
    # Reminders
    "reminders.apps.RemindersConfig",
    # Freight
    "freight.apps.FreightConfig",
    # Posts
    "posts.apps.PostsConfig",
    # Moons
    "moons.apps.MoonsConfig",
    # Market
    "market.apps.MarketConfig",
    # 'eve_auth',
    "eveuniverse",
    # 'colorfield',
    # "bootstrap_datepicker_plus",
    "lpconversion",
    # Combat log analysis
    "combatlog",
    # Standing fleet
    "standingfleet",
    # SRP
    "srp",
    # Referral links,
    "referrals",
    # User subscriptions
    "subscriptions",
    # Audit history
    "audit",
]

# Discord Login


MIDDLEWARE = [
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static files
    "django.middleware.security.SecurityMiddleware",
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
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
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
