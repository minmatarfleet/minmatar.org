"""Fill the corporation profile stats cache on release.

Corporation pages only read cached stats, so queue one full refresh when
this ships instead of waiting for the next scheduled run. The beat schedule
keeps it fresh afterwards.
"""

import logging

from django.conf import settings
from django.db import migrations

logger = logging.getLogger(__name__)

TASK = "eveonline.tasks.corporations.refresh_corporation_profile_stats"


def queue_refresh(apps, schema_editor):
    # Tests run Celery inline; don't compute stats while building test DBs.
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return
    try:
        from app.celery import (  # pylint: disable=import-outside-toplevel
            app,
        )

        app.send_task(TASK, queue="eveonline")
    except Exception:  # pylint: disable=broad-exception-caught
        # Never block a deploy on the broker; the beat schedule and the
        # on-demand refresh fill the cache anyway.
        logger.exception("Could not queue %s during migrate", TASK)


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0104_corporation_profile_media_discord"),
    ]

    operations = [
        migrations.RunPython(queue_refresh, migrations.RunPython.noop),
    ]
