"""Battle report windows the FC saves under a name."""

from __future__ import annotations

NAME_LENGTH = 64


def fc_fleet(request, fleet_id: int):
    """``(fleet, None)`` when the user is the fleet's FC, else
    ``(None, (status, body))`` for the endpoint to return."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleet, EveFleetFightTimeline

    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return None, (404, None)
    if request.user != fleet.created_by:
        return None, (403, None)
    if not EveFleetFightTimeline.objects.filter(eve_fleet=fleet).exists():
        return None, (404, None)
    return fleet, None


def default_name(start, end) -> str:
    return f"{start:%H:%M}–{end:%H:%M} ET"


def save_segment(fleet, name: str, start, end, user) -> dict:
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetBattleSegment

    if start > end:
        start, end = end, start
    name = " ".join((name or "").split())[:NAME_LENGTH]
    segment = EveFleetBattleSegment.objects.create(
        eve_fleet=fleet,
        name=name or default_name(start, end),
        start=start,
        end=end,
        created_by=user,
    )
    return {
        "id": segment.id,
        "name": segment.name,
        "start": segment.start,
        "end": segment.end,
    }
