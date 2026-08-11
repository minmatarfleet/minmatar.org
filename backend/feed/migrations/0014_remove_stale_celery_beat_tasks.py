# Remove periodic tasks for deleted feed.tasks.run_militia_rollups

from django.db import migrations

STALE_TASKS = ("feed.tasks.run_militia_rollups",)


def remove_stale_periodic_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(task__in=STALE_TASKS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0013_feed_amarr_fleet_pings"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(
            remove_stale_periodic_tasks,
            migrations.RunPython.noop,
        ),
    ]
