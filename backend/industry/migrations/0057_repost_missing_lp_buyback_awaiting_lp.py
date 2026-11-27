"""Queue the Awaiting LP posts that claims lost before commit.

Claims used to queue their Discord task inside the transaction, so a worker
could read the order as still open and post nothing. Each order now waiting
on LP gets a task that posts only when its thread has no Awaiting LP post.
"""

from django.conf import settings
from django.db import migrations

REPOST_DELAY_SECONDS = 5 * 60


def queue_reposts(apps, schema_editor):
    if getattr(settings, "TESTING", False):
        return
    # pylint: disable=import-outside-toplevel
    from app.celery import app

    order_model = apps.get_model("industry", "IndustryLoyaltyPointMarketOrder")
    order_ids = list(
        order_model.objects.filter(
            status="awaiting_lp", discord_thread_id__isnull=False
        ).values_list("pk", flat=True)
    )
    for order_id in order_ids:
        # Delayed so the workers restarted by this deploy, which know the
        # task, pick it up rather than one still running the old code.
        app.signature(
            "industry.tasks.repost_missing_lp_buyback_awaiting_lp_task",
            args=[order_id],
        ).apply_async(countdown=REPOST_DELAY_SECONDS)


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0056_industryorder_provisional"),
    ]

    operations = [
        migrations.RunPython(queue_reposts, migrations.RunPython.noop),
    ]
