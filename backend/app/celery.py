"""Celery app"""

import os

import sentry_sdk
from celery import Celery, signals
from celery.app import trace
from django.conf import settings  # noqa

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")


app = Celery("app")

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings")

# setup priorities ( 0 Highest, 9 Lowest )
app.conf.broker_transport_options = {
    "priority_steps": list(range(10)),  # setup que to have 10 steps
    "queue_order_strategy": "priority",  # setup que to use prio sorting
}
app.conf.task_default_priority = 5
app.conf.worker_prefetch_multiplier = 1

# Load task modules from all registered Django app configs.
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Remove result from default log message on task success
trace.LOG_SUCCESS = "Task %(name)s[%(id)s] succeeded in %(runtime)ss"


SENTRY_CELERY_DSN = os.environ.get("SENTRY_CELERY_DSN", None)


@signals.celeryd_init.connect
def init_sentry(**_kwargs):
    sentry_sdk.init(
        dsn=SENTRY_CELERY_DSN,
        enable_tracing=True,
        traces_sample_rate=1.0,
        environment=settings.ENV,
    )
