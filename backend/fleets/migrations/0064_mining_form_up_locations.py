"""Offer Amo and Gukarla as fleet form-up locations.

Mining fleets form up where the miners already are: the Amo Athanor
(the buyback's main location) and Gukarla - Hydra Freeport (a buyback
extra location). The form-up list is global, so every fleet host sees
them.
"""

from django.conf import settings as django_settings
from django.db import migrations

AMO_SYSTEM = "Amo"
# Gukarla - Hydra Freeport (Upwell structure, Metropolis), as seeded by
# buyback 0015.
HYDRA_FREEPORT = {
    "location_id": 1055209321122,
    "location_name": "Gukarla - Hydra Freeport",
    "short_name": "Gukarla - Hydra Freeport",
    "solar_system_id": 30003744,
    "solar_system_name": "Gukarla",
    "region_id": 10000042,
    "is_structure": True,
}


def enable_mining_form_up_locations(apps, schema_editor):
    # Test databases stay empty; tests call enable_form_up_locations.
    if getattr(django_settings, "TESTING", False):
        return
    enable_form_up_locations(apps)


def enable_form_up_locations(apps) -> list[int]:
    """Set fleets_active on both locations; return the location ids set.

    Idempotent. The Amo Athanor is taken from the buyback settings only
    when that location is in Amo, so a moved buyback never turns on
    some other station.
    """
    EveLocation = apps.get_model("eveonline", "EveLocation")
    EveBuybackSettings = apps.get_model("buyback", "EveBuybackSettings")

    location_ids = []
    defaults = {k: v for k, v in HYDRA_FREEPORT.items() if k != "location_id"}
    hydra, created = EveLocation.objects.get_or_create(
        location_id=HYDRA_FREEPORT["location_id"], defaults=defaults
    )
    if not created and getattr(hydra, "deleted", None):
        hydra.deleted = None
        hydra.save(update_fields=["deleted"])
    location_ids.append(hydra.location_id)

    buyback = EveBuybackSettings.objects.filter(pk=1).first()
    amo = buyback.location if buyback else None
    if amo is not None and amo.solar_system_name == AMO_SYSTEM:
        location_ids.append(amo.location_id)

    EveLocation.objects.filter(location_id__in=location_ids).update(
        fleets_active=True
    )
    return location_ids


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("fleets", "0063_invite_confidence"),
        ("buyback", "0015_accepted_locations"),
        ("eveonline", "0117_eve_location_industry_delivery"),
    ]

    operations = [
        migrations.RunPython(enable_mining_form_up_locations, noop_reverse),
    ]
