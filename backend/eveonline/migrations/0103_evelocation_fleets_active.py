from django.db import migrations, models


def enable_fleets_active_locations(apps, schema_editor):
    EveLocation = apps.get_model("eveonline", "EveLocation")
    EveFleetAudience = apps.get_model("fleets", "EveFleetAudience")

    location_ids = set(
        EveLocation.objects.filter(staging_active=True).values_list(
            "location_id", flat=True
        )
    )
    audience_staging_ids = EveFleetAudience.objects.exclude(
        staging_location_id__isnull=True
    ).values_list("staging_location_id", flat=True)
    location_ids.update(audience_staging_ids)

    jita_ids = EveLocation.objects.filter(
        models.Q(short_name__iexact="Jita")
        | models.Q(solar_system_name__iexact="Jita")
    ).values_list("location_id", flat=True)
    location_ids.update(jita_ids)

    if location_ids:
        EveLocation.objects.filter(location_id__in=location_ids).update(
            fleets_active=True
        )


class Migration(migrations.Migration):

    dependencies = [
        ("fleets", "0042_npsi_event_source"),
        ("eveonline", "0102_character_corporation_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="evelocation",
            name="fleets_active",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="Location may be selected as fleet form-up on the schedule.",
            ),
        ),
        migrations.RunPython(
            enable_fleets_active_locations,
            migrations.RunPython.noop,
        ),
    ]
