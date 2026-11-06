"""GET /commanders: the Fleet Commanders tribe group, as the Commanders tab shows it."""

from typing import List

from django.utils import timezone

from app.eve_time import month_bounds
from authentication import AuthBearer
from eveonline.helpers.characters.identity import (
    primary_characters_for_users,
)
from eveonline.models import EveCorporation
from timezones.services import timezone_tags_for
from tribes.models import TribeGroupMembership

from fleets.endpoints.schemas import EveFleetCommander
from fleets.helpers.metrics import fleets_led_by_user, led_fleets

PATH = "/commanders"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetCommander]},
    "summary": "Fleet Commanders tribe members: level, timezone, recent fleets",
}

FLEET_COMMANDERS_GROUP_CODE = "pulse.fleet-commanders"


def get_fleet_commanders(request):
    memberships = list(
        TribeGroupMembership.objects.filter(
            tribe_group__code=FLEET_COMMANDERS_GROUP_CODE,
            status=TribeGroupMembership.STATUS_ACTIVE,
        ).select_related("rank")
    )
    user_ids = [m.user_id for m in memberships]

    now = timezone.now()
    month_start, month_end = month_bounds()
    month_counts = {
        row["created_by_id"]: row["fleet_count"]
        for row in fleets_led_by_user(led_fleets(month_start, month_end))
    }
    last_led = {}
    for fleet in (
        led_fleets(end=now)
        .filter(created_by_id__in=user_ids)
        .order_by("-start_time")
        .values("created_by_id", "start_time")
    ):
        last_led.setdefault(fleet["created_by_id"], fleet["start_time"])

    mains = primary_characters_for_users(user_ids)
    corp_ids = {
        int(main.corporation_id)
        for main in mains.values()
        if main.corporation_id is not None
    }
    corp_names = {
        c.corporation_id: c.name
        for c in EveCorporation.objects.filter(corporation_id__in=corp_ids)
    }
    tags = timezone_tags_for(user_ids)

    out: List[EveFleetCommander] = []
    for membership in memberships:
        uid = membership.user_id
        main = mains.get(uid)
        corp_id = (
            int(main.corporation_id)
            if main and main.corporation_id is not None
            else None
        )
        out.append(
            EveFleetCommander(
                user_id=uid,
                primary_character_id=main.character_id if main else None,
                primary_character_name=main.character_name if main else None,
                corporation_id=corp_id,
                corporation_name=corp_names.get(corp_id),
                rank_name=membership.rank.name if membership.rank else None,
                rank_order=(
                    membership.rank.sort_order if membership.rank else None
                ),
                timezone=tags[uid],
                fleets_this_month=month_counts.get(uid, 0),
                last_led=last_led.get(uid),
            )
        )

    # Most recently active first; pilots who never led sink to the bottom.
    out.sort(
        key=lambda c: c.last_led.timestamp() if c.last_led else 0, reverse=True
    )
    return out
