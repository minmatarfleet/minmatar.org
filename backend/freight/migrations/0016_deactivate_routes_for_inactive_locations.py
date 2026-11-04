from django.db import migrations
from django.db.models import Q


def deactivate_routes_for_inactive_locations(apps, schema_editor):
    """Turn off routes that still touch a location that is not a freight stop.

    Locations such as Auner and Gukarla were already freight-inactive while
    their routes stayed bookable. Disabling a location now does this on save;
    this pass catches the rows that were left on.
    """
    EveFreightRoute = apps.get_model("freight", "EveFreightRoute")
    EveLocation = apps.get_model("eveonline", "EveLocation")
    locations = getattr(EveLocation, "all_objects", EveLocation.objects)
    inactive_ids = locations.filter(freight_active=False).values("pk")
    (
        EveFreightRoute.objects.filter(active=True)
        .filter(
            Q(origin_location_id__in=inactive_ids)
            | Q(destination_location_id__in=inactive_ids)
        )
        .update(active=False)
    )


class Migration(migrations.Migration):

    dependencies = [
        ("freight", "0015_evefreightroute_xl_fee_millions"),
        ("eveonline", "0110_corporation_discord_bot"),
    ]

    operations = [
        migrations.RunPython(
            deactivate_routes_for_inactive_locations,
            migrations.RunPython.noop,
        ),
    ]
