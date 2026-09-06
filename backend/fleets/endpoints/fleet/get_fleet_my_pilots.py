"""GET /{fleet_id}/my-pilots — the caller's characters with recent fleet activity and their ship pick."""

from datetime import timedelta
from typing import List

from django.db.models import Max
from django.utils import timezone

from authentication import AuthBearer
from eveonline.helpers.characters import user_characters

from fleets.endpoints.helpers import _fleet_authorized
from fleets.endpoints.schemas import MyFleetPilotResponse, ShipSelection
from fleets.models import (
    EveFleet,
    EveFleetInstanceMember,
    EveFleetShipVolunteer,
)

PATH = "/{fleet_id}/my-pilots"
METHOD = "get"
RECENT_DAYS = 30
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[MyFleetPilotResponse], 403: None, 404: None},
    "description": (
        "The caller's characters, flagged when they joined a tracked fleet in "
        "the last 30 days, with the ship each one is currently volunteered for."
    ),
}


def get_fleet_my_pilots(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None

    characters = list(user_characters(request.user))
    character_ids = [c.character_id for c in characters]
    since = timezone.now() - timedelta(days=RECENT_DAYS)
    last_seen = dict(
        EveFleetInstanceMember.objects.filter(
            character_id__in=character_ids, join_time__gte=since
        )
        .values_list("character_id")
        .annotate(last=Max("join_time"))
        .values_list("character_id", "last")
    )
    selections = {
        v.character_id: ShipSelection(
            character_id=v.character_id,
            fitting_id=v.fitting_id,
            fleet_fitting_id=v.fleet_fitting_id,
        )
        for v in EveFleetShipVolunteer.objects.filter(
            eve_fleet=fleet, character_id__in=character_ids
        ).order_by("id")
    }
    # Recently active characters first, most recent fleet first.
    characters.sort(
        key=lambda c: (
            c.character_id not in last_seen,
            -(
                last_seen[c.character_id].timestamp()
                if c.character_id in last_seen
                else 0
            ),
            c.character_name.lower(),
        )
    )
    return [
        MyFleetPilotResponse(
            character_id=c.character_id,
            character_name=c.character_name,
            recent_fleets=c.character_id in last_seen,
            selection=selections.get(c.character_id),
        )
        for c in characters
    ]
