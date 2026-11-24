"""Seed the fleet voice options and point existing fleets at the default.

Every fleet MOTD so far linked the alliance Discord, so existing fleets get
that option and their MOTD doesn't change. Mumble is created inactive: no
fleet can pick it until go-live switches it on in the admin.
"""

from django.db import migrations

DISCORD_NAME = "Minmatar Fleet Discord"
MUMBLE_NAME = "Mumble"


def seed(apps, schema_editor):
    FleetVoiceOption = apps.get_model("fleets", "FleetVoiceOption")
    EveFleet = apps.get_model("fleets", "EveFleet")
    discord, _ = FleetVoiceOption.objects.get_or_create(
        name=DISCORD_NAME,
        defaults={
            "kind": "discord",
            "link": "https://discord.gg/minmatar",
            "is_default": True,
            "is_active": True,
            "order": 0,
        },
    )
    FleetVoiceOption.objects.get_or_create(
        name=MUMBLE_NAME,
        defaults={
            "kind": "mumble",
            "is_default": False,
            "is_active": False,
            "order": 10,
        },
    )
    EveFleet.objects.filter(voice_option__isnull=True).update(
        voice_option=discord
    )


class Migration(migrations.Migration):

    dependencies = [
        ("fleets", "0068_fleetvoiceoption_evefleet_voice_option"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
