from django.conf import settings
from django.db import migrations


def close_orphan_threads(apps, schema_editor):
    if getattr(settings, "TESTING", False):
        return
    from industry.helpers.lp_buyback_discord import (
        ORPHAN_LP_BUYBACK_THREAD_IDS,
        close_lp_buyback_thread_id,
    )

    for thread_id in ORPHAN_LP_BUYBACK_THREAD_IDS:
        close_lp_buyback_thread_id(thread_id)


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0046_delete_miningupgradecompletion"),
    ]

    operations = [
        migrations.RunPython(
            close_orphan_threads,
            migrations.RunPython.noop,
        ),
    ]
