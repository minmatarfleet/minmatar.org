"""GET /commander-metrics — FC fleet counts for current calendar month."""

from typing import List

from app.eve_time import month_bounds
from authentication import AuthBearer
from eveonline.helpers.characters.identity import (
    primary_characters_for_users,
)
from eveonline.models import EveCorporation

from fleets.endpoints.schemas import EveFleetCommanderMetric
from fleets.helpers.metrics import fleets_led_by_user, led_fleets

PATH = "/commander-metrics"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetCommanderMetric]},
    "summary": "Fleet counts per commander for the current calendar month",
}


def get_fleet_commander_metrics(request):
    month_start, month_end = month_bounds()
    rows = fleets_led_by_user(led_fleets(month_start, month_end))

    user_ids = [r["created_by_id"] for r in rows]
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

    out: List[EveFleetCommanderMetric] = []
    for row in rows:
        uid = row["created_by_id"]
        char = mains.get(uid)
        corp_id = (
            int(char.corporation_id)
            if char and char.corporation_id is not None
            else None
        )
        corp_name = corp_names.get(corp_id) if corp_id is not None else None
        out.append(
            EveFleetCommanderMetric(
                user_id=uid,
                primary_character_id=char.character_id if char else None,
                primary_character_name=char.character_name if char else None,
                corporation_id=corp_id,
                corporation_name=corp_name,
                fleet_count=row["fleet_count"],
            )
        )
    return 200, out
