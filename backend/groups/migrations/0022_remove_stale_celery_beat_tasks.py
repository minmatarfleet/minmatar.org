# Remove periodic tasks for deleted groups.tasks.remove_teams / remove_sigs

from django.db import migrations

STALE_TASKS = (
    "groups.tasks.remove_teams",
    "groups.tasks.remove_sigs",
)


def remove_stale_periodic_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(task__in=STALE_TASKS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0021_remove_team_sig_models"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(
            remove_stale_periodic_tasks,
            migrations.RunPython.noop,
        ),
    ]
