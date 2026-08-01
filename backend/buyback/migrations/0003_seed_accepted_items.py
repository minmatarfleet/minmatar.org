from django.db import migrations

from buyback.models import (
    DEFAULT_ACCEPTED_CATEGORIES,
    DEFAULT_EXCLUSIONS,
    DEFAULT_LEADING_TEXT,
)


def seed_and_refresh_settings(apps, schema_editor):
    from buyback.helpers.accepted_items import seed_accepted_items

    seed_accepted_items()

    EveBuybackSettings = apps.get_model("buyback", "EveBuybackSettings")
    EveBuybackSettings.objects.filter(pk=1).update(
        accepted_categories=list(DEFAULT_ACCEPTED_CATEGORIES),
        exclusions=list(DEFAULT_EXCLUSIONS),
        leading_text=DEFAULT_LEADING_TEXT,
    )


def noop_reverse(apps, schema_editor):
    BuybackAcceptedItem = apps.get_model("buyback", "BuybackAcceptedItem")
    BuybackAcceptedItem.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("buyback", "0002_accepted_items"),
    ]

    operations = [
        migrations.RunPython(seed_and_refresh_settings, noop_reverse),
    ]
