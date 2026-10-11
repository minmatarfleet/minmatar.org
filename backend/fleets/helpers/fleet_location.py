"""Resolve EveLocation for fleet form-up."""

from __future__ import annotations

from eveonline.models import EveLocation

from fleets.models import EveFleet


def match_fleets_active_location(text: str) -> EveLocation | None:
    needle = (text or "").strip().lower()
    if not needle:
        return None

    for location in EveLocation.objects.filter(fleets_active=True):
        if location.short_name.lower() == needle:
            return location
        if location.solar_system_name.lower() == needle:
            return location
        if location.location_name.lower().startswith(needle):
            return location
    return None


def resolve_scheduled_fleet_location(
    location_id: int | None,
) -> EveLocation | tuple[int, dict]:
    if location_id:
        location = EveLocation.objects.filter(
            location_id=location_id, fleets_active=True
        ).first()
        if location is None:
            return 400, {
                "detail": "Location does not exist or is not available for fleets"
            }
        return location

    location = EveLocation.objects.filter(staging_active=True).first()
    if location is None:
        return 400, {"detail": "No active staging location configured"}
    return location


def default_staging_location() -> EveLocation | None:
    return EveLocation.objects.filter(staging_active=True).first()


def backfill_missing_fleet_locations() -> int:
    """Assign staging to fleets with no form-up location. Returns rows updated."""
    staging = default_staging_location()
    if staging is None:
        return 0
    return EveFleet.objects.filter(location__isnull=True).update(
        location=staging
    )
