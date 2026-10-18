"""#warzone-pings is now #pings in Discord; follow the rename."""

from django.db import migrations

PINGS_CHANNEL_ID = 1064548000397021224
RENAMES = {"#warzone-pings": "#pings", "warzone-pings": "pings"}


def _rename(apps, mapping):
    EveFleetAudience = apps.get_model("fleets", "EveFleetAudience")
    audiences = EveFleetAudience.objects.filter(
        discord_channel_id=PINGS_CHANNEL_ID
    )
    # The channel name shows in the fleet form; rename the audience too if
    # it was named after the channel.
    for old, new in mapping.items():
        audiences.filter(discord_channel_name=old).update(
            discord_channel_name=new
        )
        audiences.filter(name=old).update(name=new)


def forwards(apps, schema_editor):
    _rename(apps, RENAMES)


def backwards(apps, schema_editor):
    _rename(apps, {new: old for old, new in RENAMES.items()})


class Migration(migrations.Migration):

    dependencies = [
        ("fleets", "0050_tribe_publishing"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
