"""Tribe groups that required the Campaign token type now require Faction Warfare.

Campaign is kept as a legacy alias with the same scopes, so this only moves
stored values onto the name the admin form offers.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    TribeGroup.objects.filter(required_token_type="Campaign").update(
        required_token_type="FactionWarfare"
    )


def backwards(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    TribeGroup.objects.filter(required_token_type="FactionWarfare").update(
        required_token_type="Campaign"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("tribes", "0040_merge_20261004_1310"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
