"""Celery app

Queues and routing come from ``app.queues``; every task's base class is
``app.task_base.AppTask``. See docs/architecture/celery-queues.md.
"""

import os

from celery import Celery, signals
from celery.app import trace
from django.conf import settings  # noqa
from kombu import Queue

from app.monitoring import init_sentry
from app.queues import FAST_LANE, QUEUES, route_task

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")


app = Celery("app", task_cls="app.task_base:AppTask")

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings")

if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = getattr(
        settings, "CELERY_TASK_EAGER_PROPAGATES", True
    )

# Set here so workers and producers (web, beat, admin) agree. The router
# also covers send_task and beat; nothing else passes queue=.
app.conf.task_queues = tuple(Queue(name, routing_key=name) for name in QUEUES)
app.conf.task_default_queue = FAST_LANE
app.conf.task_routes = (route_task,)

# Celery 6+: use this for startup retries; silences deprecation warning in 5.x
app.conf.broker_connection_retry_on_startup = True

# setup priorities ( 0 Highest, 9 Lowest )
app.conf.broker_transport_options = {
    "priority_steps": list(range(10)),  # setup que to have 10 steps
    "queue_order_strategy": "priority",  # setup que to use prio sorting
}
app.conf.task_default_priority = 5
app.conf.worker_prefetch_multiplier = 1

# celery_once: django-eveuniverse's tasks use QueueOnce. Our own tasks get
# their dedupe from AppTask.
app.conf.ONCE = {
    "backend": "app.celery_once_backend.DjangoBackend",
    "settings": {},
}

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Remove result from default log message on task success
trace.LOG_SUCCESS = "Task %(name)s[%(id)s] succeeded in %(runtime)ss"


@signals.celeryd_init.connect
def init_sentry_for_worker(**_kwargs):
    init_sentry(component="worker", environment=settings.ENV)
