"""Resolve EVE location IDs to display names."""

import logging

from eveuniverse.models import EveStation

from eveonline.client import EsiClient
from eveonline.models import EveLocation

logger = logging.getLogger(__name__)


def resolve_location_name(
    location_id: int | None, location_type: str | None = None
) -> str:
    """
    Resolve a station or structure ID to a human-readable name.
    Returns an empty string when the ID is missing or resolution fails.
    """
    if not location_id:
        return ""

    location = EveLocation.objects.filter(location_id=location_id).first()
    if location:
        return location.location_name

    if location_type == "station" or (
        location_type is None and location_id < 1_000_000_000_000
    ):
        try:
            station = EveStation.objects.get_or_create_esi(id=location_id)[0]
            return station.name or ""
        except Exception:
            logger.debug(
                "Could not resolve station %s via eveuniverse",
                location_id,
                exc_info=True,
            )

    try:
        response = EsiClient(None).resolve_universe_names([location_id])
        if response.success():
            results = response.results() or []
            if results:
                return results[0].get("name") or ""
    except Exception:
        logger.debug(
            "Could not resolve location %s via ESI names",
            location_id,
            exc_info=True,
        )

    return ""
