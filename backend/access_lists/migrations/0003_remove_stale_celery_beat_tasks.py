# Beat still enqueues the deleted executor access-list sync task.

from django.db import migrations

STALE_TASKS = ("access_lists.tasks.sync_executor_access_lists_task",)


def remove_stale_periodic_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(task__in=STALE_TASKS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("access_lists", "0002_delete_eveaccesslist_models"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(
            remove_stale_periodic_tasks,
            migrations.RunPython.noop,
        ),
    ]
