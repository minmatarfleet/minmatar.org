from django.db import migrations, models


def backfill_fleet_locations_from_audience(apps, schema_editor):
    """Copy audience staging onto fleets that never had location_id set."""
    EveFleet = apps.get_model("fleets", "EveFleet")
    EveLocation = apps.get_model("eveonline", "EveLocation")

    staging_location_id = (
        EveLocation.objects.filter(staging_active=True)
        .values_list("location_id", flat=True)
        .first()
    )

    for fleet in EveFleet.objects.filter(
        location_id__isnull=True
    ).select_related("audience"):
        audience = fleet.audience
        if audience is not None and audience.staging_location_id is not None:
            fleet.location_id = audience.staging_location_id
            fleet.save(update_fields=["location_id"])
            continue
        if staging_location_id is not None:
            fleet.location_id = staging_location_id
            fleet.save(update_fields=["location_id"])


def backfill_remaining_fleet_locations(apps, schema_editor):
    """Any fleet still missing location gets the active staging system."""
    EveFleet = apps.get_model("fleets", "EveFleet")
    EveLocation = apps.get_model("eveonline", "EveLocation")

    staging_location_id = (
        EveLocation.objects.filter(staging_active=True)
        .values_list("location_id", flat=True)
        .first()
    )
    if staging_location_id is None:
        return

    EveFleet.objects.filter(location_id__isnull=True).update(
        location_id=staging_location_id
    )


def configure_unaligned_npsi_source(apps, schema_editor):
    EveLocation = apps.get_model("eveonline", "EveLocation")
    NpsiEventSource = apps.get_model("fleets", "NpsiEventSource")

    jita = (
        EveLocation.objects.filter(fleets_active=True)
        .filter(
            models.Q(short_name__iexact="Jita")
            | models.Q(solar_system_name__iexact="Jita")
        )
        .order_by("location_id")
        .first()
    )
    defaults = {"default_type": "npsi"}
    if jita is not None:
        defaults["default_location_id"] = jita.location_id

    NpsiEventSource.objects.filter(name="Unaligned").update(**defaults)


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0103_evelocation_fleets_active"),
        ("fleets", "0042_npsi_event_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evefleet",
            name="type",
            field=models.CharField(
                choices=[
                    ("strategic", "Strategic Operation"),
                    ("non_strategic", "Non Strategic Operation"),
                    ("training", "Training Operation"),
                    ("npsi", "NPSI"),
                ],
                max_length=32,
            ),
        ),
        migrations.RunPython(
            backfill_fleet_locations_from_audience,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="evefleetaudience",
            name="staging_location",
        ),
        migrations.RunPython(
            backfill_remaining_fleet_locations,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="npsieventsource",
            name="default_type",
            field=models.CharField(
                choices=[
                    ("strategic", "Strategic Operation"),
                    ("non_strategic", "Non Strategic Operation"),
                    ("training", "Training Operation"),
                    ("npsi", "NPSI"),
                ],
                default="npsi",
                max_length=32,
            ),
        ),
        migrations.RunPython(
            configure_unaligned_npsi_source,
            migrations.RunPython.noop,
        ),
    ]
