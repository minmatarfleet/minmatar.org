# Fleet Commanders tribe group under Pulse

from django.db import migrations


def create_fleet_commanders_group(apps, schema_editor):
    Tribe = apps.get_model("tribes", "Tribe")
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    tribe = Tribe.objects.filter(slug="pulse", is_active=True).first()
    if not tribe:
        return
    if TribeGroup.objects.filter(code="pulse.fleet-commanders").exists():
        return
    TribeGroup.objects.create(
        tribe=tribe,
        name="Fleet Commanders",
        code="pulse.fleet-commanders",
        description=(
            "FC development, fleet coverage, and commander recognition."
        ),
        is_active=True,
    )


def remove_fleet_commanders_group(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    TribeGroup.objects.filter(code="pulse.fleet-commanders").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0021_tribegroup_code"),
    ]

    operations = [
        migrations.RunPython(
            create_fleet_commanders_group,
            remove_fleet_commanders_group,
        ),
    ]
