"""Make EveStructurePing.notification_id unique.

Two workers could store the same notification at once, and get_or_create then
raised MultipleObjectsReturned on every later lookup (MINMATAR-CELERY-M4).
Duplicates are removed first: the row that reached Discord is kept, otherwise
the oldest.
"""

from django.db import migrations, models
from django.db.models import Count


def remove_duplicate_pings(apps, schema_editor):
    ping_model = apps.get_model("structures", "EveStructurePing")
    duplicated = (
        ping_model.objects.values("notification_id")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .values_list("notification_id", flat=True)
    )
    for notification_id in list(duplicated):
        ids = list(
            ping_model.objects.filter(notification_id=notification_id)
            .order_by("-discord_success", "id")
            .values_list("id", flat=True)
        )
        ping_model.objects.filter(id__in=ids[1:]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0024_locations_public_by_default"),
    ]

    operations = [
        migrations.RunPython(
            remove_duplicate_pings, migrations.RunPython.noop, elidable=True
        ),
        migrations.AlterField(
            model_name="evestructureping",
            name="notification_id",
            field=models.BigIntegerField(unique=True),
        ),
    ]
