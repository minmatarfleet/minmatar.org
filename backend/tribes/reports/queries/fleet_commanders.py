"""Fleet commander leaderboard (fleets led per user)."""

from django.db.models import Count
from datetime import datetime

from django.utils import timezone

from eveonline.models import EveCorporation, EvePlayer
from fleets.models import EveFleet
from tribes.reports.roster import roster_user_ids
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = [
    "user_id",
    "primary_character_id",
    "primary_character_name",
    "corporation_id",
    "corporation_name",
    "fleet_count",
]


def run_fleet_commanders_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    start_dt = timezone.make_aware(
        datetime.combine(period.start, datetime.min.time())
    )
    end_dt = timezone.make_aware(
        datetime.combine(period.end, datetime.max.time())
    )

    qs = EveFleet.objects.filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        created_by_id__isnull=False,
    ).exclude(status="cancelled")

    if scope == ReportScope.ROSTER:
        roster_ids = roster_user_ids(tribe_group)
        if not roster_ids:
            return [], {"total_fleets": 0}, COLUMNS
        qs = qs.filter(created_by_id__in=roster_ids)

    rows_qs = (
        qs.values("created_by_id")
        .annotate(fleet_count=Count("id"))
        .order_by("-fleet_count", "created_by_id")
    )

    user_ids = [r["created_by_id"] for r in rows_qs]
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

    rows = []
    total_fleets = 0
    for row in rows_qs:
        uid = row["created_by_id"]
        count = row["fleet_count"]
        total_fleets += count
        player = players.get(uid)
        char = player.primary_character if player else None
        corp_id = (
            int(char.corporation_id)
            if char and char.corporation_id is not None
            else None
        )
        rows.append(
            {
                "user_id": uid,
                "primary_character_id": char.character_id if char else None,
                "primary_character_name": (
                    char.character_name if char else None
                ),
                "corporation_id": corp_id,
                "corporation_name": (
                    corp_names.get(corp_id) if corp_id else None
                ),
                "fleet_count": count,
            }
        )

    return rows, {"total_fleets": total_fleets}, COLUMNS
