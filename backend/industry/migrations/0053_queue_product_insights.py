"""Fill the supply chain product insights cache on release.

Product pages only read cached insights, so queue one full refresh when
this ships instead of making the first visitor wait for it. The beat
schedule keeps it fresh afterwards.
"""

import logging

from django.conf import settings
from django.db import migrations

logger = logging.getLogger(__name__)

TASK = "industry.tasks.refresh_product_insights_task"


def queue_refresh(apps, schema_editor):
    # Tests run Celery inline; don't compute insights while building test DBs.
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return
    try:
        from app.celery import (  # pylint: disable=import-outside-toplevel
            app,
        )

        app.send_task(TASK, queue="celery")
    except Exception:  # pylint: disable=broad-exception-caught
        # Never block a deploy on the broker; the beat schedule and the
        # on-demand refresh fill the cache anyway.
        logger.exception("Could not queue %s during migrate", TASK)


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0052_lp_order_status_changed_at"),
    ]

    operations = [
        migrations.RunPython(queue_refresh, migrations.RunPython.noop),
    ]
