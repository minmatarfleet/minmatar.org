import logging
from datetime import timedelta

from django.db.models import Q

from eveonline.helpers.characters import user_primary_character
from fleets.models import EveFleet

logger = logging.getLogger(__name__)

DESCRIPTION_SNIPPET_MAX = 200


def description_snippet(description: str | None) -> str:
    d = description or ""
    if len(d) <= DESCRIPTION_SNIPPET_MAX:
        return d
    limit = DESCRIPTION_SNIPPET_MAX - 3
    return d[:limit] + "..."


def get_candidate_fleets_queryset(kill_time):
    """
    Fleets whose scheduled start or any EveFleetInstance activity overlaps
    [kill_time - 6h, kill_time + 6h]. Excludes cancelled fleets.
    """
    window_start = kill_time - timedelta(hours=6)
    window_end = kill_time + timedelta(hours=6)

    scheduled_in_window = Q(
        start_time__gte=window_start,
        start_time__lte=window_end,
    )
    instance_overlaps = Q(
        evefleetinstance__start_time__lte=window_end,
    ) & (
        Q(evefleetinstance__end_time__isnull=True)
        | Q(evefleetinstance__end_time__gte=window_start)
    )

    return (
        EveFleet.objects.filter(scheduled_in_window | instance_overlaps)
        .exclude(status="cancelled")
        .distinct()
        .select_related("audience", "created_by")
        .order_by("-start_time")
    )


def serialize_candidate_fleet(fleet: EveFleet) -> dict:
    """Match fleets API shape where practical; add FC name for UI."""
    audience_label = fleet.audience.name if fleet.audience else ""
    fleet_commander_user_id = fleet.created_by.id if fleet.created_by else 0
    fleet_commander_name = None
    if fleet.created_by:
        pc = user_primary_character(fleet.created_by)
        if pc:
            fleet_commander_name = pc.character_name
    return {
        "id": fleet.id,
        "type": fleet.type,
        "audience": audience_label,
        "start_time": fleet.start_time,
        "description_snippet": description_snippet(fleet.description),
        "fleet_commander": fleet_commander_user_id,
        "fleet_commander_name": fleet_commander_name,
    }
