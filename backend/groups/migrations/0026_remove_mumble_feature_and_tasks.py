# Remove Mumble feature row and Celery beat task after hard-delete.

from django.db import migrations

STALE_TASKS = ("mumble.tasks.set_mumble_usernames",)


def remove_mumble_artifacts(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(task__in=STALE_TASKS).delete()

    PilotFeature = apps.get_model("groups", "PilotFeature")
    PilotFeature.objects.filter(code="mumble.access").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0025_remove_stale_reminder_celery_beat_tasks"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(
            remove_mumble_artifacts,
            migrations.RunPython.noop,
        ),
    ]
