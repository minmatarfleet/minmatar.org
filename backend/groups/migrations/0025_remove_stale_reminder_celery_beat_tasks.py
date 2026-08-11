# Remove periodic tasks for deleted groups reminder tasks

from django.db import migrations

STALE_TASKS = (
    "groups.tasks.create_sig_request_reminders",
    "groups.tasks.create_team_request_reminders",
)


def remove_stale_periodic_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(task__in=STALE_TASKS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0024_pilot_feature"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(
            remove_stale_periodic_tasks,
            migrations.RunPython.noop,
        ),
    ]
