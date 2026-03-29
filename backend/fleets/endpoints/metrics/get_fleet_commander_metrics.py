"""GET /commander-metrics — FC fleet counts for current calendar month."""

from typing import List

from django.db.models import Count
from django.utils import timezone

from authentication import AuthBearer
from eveonline.models import EveCorporation, EvePlayer

from fleets.endpoints.schemas import EveFleetCommanderMetric
from fleets.models import EveFleet


def _calendar_month_bounds():
    now = timezone.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


PATH = "/commander-metrics"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetCommanderMetric]},
    "summary": "Fleet counts per commander for the current calendar month",
}


def get_fleet_commander_metrics(request):
    month_start, month_end = _calendar_month_bounds()
    rows = (
        EveFleet.objects.filter(
            start_time__gte=month_start,
            start_time__lt=month_end,
            created_by_id__isnull=False,
        )
        .exclude(status="cancelled")
        .values("created_by_id")
        .annotate(fleet_count=Count("id"))
        .order_by("-fleet_count", "created_by_id")
    )

    user_ids = [r["created_by_id"] for r in rows]
    players = {
        p.user_id: p
        for p in EvePlayer.objects.filter(user_id__in=user_ids).select_related(
            "primary_character"
        )
    }

    corp_ids = {
        int(p.primary_character.corporation_id)
        for p in players.values()
        if p
        and p.primary_character
        and p.primary_character.corporation_id is not None
    }
    corp_names = {
        c.corporation_id: c.name
        for c in EveCorporation.objects.filter(corporation_id__in=corp_ids)
    }

    out: List[EveFleetCommanderMetric] = []
    for row in rows:
        uid = row["created_by_id"]
        player = players.get(uid)
        char = player.primary_character if player else None
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
