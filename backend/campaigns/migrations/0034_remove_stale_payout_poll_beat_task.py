# Remove the beat entry for campaigns.tasks.poll_campaign_payouts, replaced by
# process_campaign_payouts in #3110. DatabaseScheduler keeps the old row and
# beat kept sending the unregistered task (MINMATAR-CELERY-FR).

from django.db import migrations

STALE_TASKS = ("campaigns.tasks.poll_campaign_payouts",)


def remove_stale_periodic_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(task__in=STALE_TASKS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0033_remove_payouts_polled_at"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(
            remove_stale_periodic_tasks,
            migrations.RunPython.noop,
        ),
    ]
