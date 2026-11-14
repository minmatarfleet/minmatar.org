from django.conf import settings as django_settings
from django.db import migrations, models

# Auner VIII - Moon 10 - Thukker Mix Factory (NPC station, Heimatar).
THUKKER_MIX_FACTORY = {
    "location_id": 60014131,
    "location_name": "Auner VIII - Moon 10 - Thukker Mix Factory",
    "short_name": "Auner - Thukker Mix Factory",
    "solar_system_id": 30002059,
    "solar_system_name": "Auner",
    "region_id": 10000042,
    "is_structure": False,
}
# Gukarla - Hydra Freeport (Upwell structure, Metropolis).
HYDRA_FREEPORT = {
    "location_id": 1055209321122,
    "location_name": "Gukarla - Hydra Freeport",
    "short_name": "Gukarla - Hydra Freeport",
    "solar_system_id": 30003744,
    "solar_system_name": "Gukarla",
    "region_id": 10000042,
    "is_structure": True,
}


def add_accepted_locations(apps, schema_editor):
    # Test databases stay empty; tests call seed_accepted_locations.
    if getattr(django_settings, "TESTING", False):
        return
    seed_accepted_locations(apps)


def seed_accepted_locations(apps):
    """Idempotent: reuse a row that already exists, even soft-deleted."""
    EveLocation = apps.get_model("eveonline", "EveLocation")
    EveBuybackSettings = apps.get_model("buyback", "EveBuybackSettings")
    settings, _ = EveBuybackSettings.objects.get_or_create(pk=1)
    for data in (THUKKER_MIX_FACTORY, HYDRA_FREEPORT):
        defaults = {k: v for k, v in data.items() if k != "location_id"}
        location, created = EveLocation.objects.get_or_create(
            location_id=data["location_id"], defaults=defaults
        )
        if not created and getattr(location, "deleted", None):
            location.deleted = None
            location.save(update_fields=["deleted"])
        settings.extra_locations.add(location)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("buyback", "0014_purchase_order_stall_clock"),
        ("eveonline", "0111_evelocation_freight_active_help_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="evebuybacksettings",
            name="extra_locations",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Further stations or structures where contracts are "
                    "accepted, listed after the main location in the "
                    "contract walkthrough."
                ),
                related_name="buyback_extra_settings",
                to="eveonline.evelocation",
            ),
        ),
        migrations.RunPython(add_accepted_locations, noop_reverse),
    ]
