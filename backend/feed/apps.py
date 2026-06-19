# pylint: disable=import-outside-toplevel
from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class FeedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "feed"
    verbose_name = "Activity Feed"

    def ready(self):
        from feed.helpers.monitored_systems import (
            invalidate_monitored_systems_cache,
        )
        from feed.models import FeedMonitoredSystem

        def _invalidate(*args, **kwargs):
            invalidate_monitored_systems_cache()

        post_save.connect(_invalidate, sender=FeedMonitoredSystem)
        post_delete.connect(_invalidate, sender=FeedMonitoredSystem)
