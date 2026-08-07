# Generated manually for deleted/expired private market contracts stuck as outstanding.

from django.db import migrations
from django.utils import timezone


def expire_stale_outstanding(apps, schema_editor):
    """Expire outstanding market contracts whose expiry date is already past."""
    EveMarketContract = apps.get_model("market", "EveMarketContract")
    EveMarketContract.objects.filter(
        status="outstanding",
        expires_at__lt=timezone.now(),
    ).update(status="expired")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0034_attributed_order"),
    ]

    operations = [
        migrations.RunPython(expire_stale_outstanding, noop),
    ]
