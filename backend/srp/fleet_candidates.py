from datetime import timedelta

from django.db.models import Q

from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation, EveCharacter
from fleets.models import EveFleet


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
        .select_related("created_by")
        .order_by("-start_time")
    )


def _fleet_commander_from_pc(
    pc: EveCharacter | None, corp_names: dict[int, str]
) -> dict:
    if not pc:
        return {
            "character_id": 0,
            "character_name": "",
            "corporation_id": 0,
            "corporation_name": "",
        }
    corp_id = int(pc.corporation_id) if pc.corporation_id is not None else 0
    corp_name = corp_names.get(corp_id, "") if corp_id else ""
    return {
        "character_id": pc.character_id,
        "character_name": pc.character_name or "",
        "corporation_id": corp_id,
        "corporation_name": corp_name,
    }


def serialize_candidate_fleets(fleets_qs) -> list[dict]:
    """Build API dicts for resolve-killmail candidate fleets."""
    fleets = list(fleets_qs)
    corp_ids: set[int] = set()
    commanders: list[EveCharacter | None] = []
    for fleet in fleets:
        if not fleet.created_by:
            commanders.append(None)
            continue
        pc = user_primary_character(fleet.created_by)
        commanders.append(pc)
        if pc and pc.corporation_id is not None:
            corp_ids.add(int(pc.corporation_id))

    corp_names: dict[int, str] = {}
    if corp_ids:
        corp_names = {
            row["corporation_id"]: row["name"] or ""
            for row in EveCorporation.objects.filter(
                corporation_id__in=corp_ids
            ).values("corporation_id", "name")
        }

    return [
        {
            "id": fleet.id,
            "type": fleet.type,
            "start_time": fleet.start_time,
            "objective": fleet.objective or "",
            "fleet_commander": _fleet_commander_from_pc(pc, corp_names),
        }
        for fleet, pc in zip(fleets, commanders)
    ]
