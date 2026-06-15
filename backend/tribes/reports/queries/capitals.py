"""Capitals combat activity: kills, losses, and fleet participation by qualifying ship types."""

from collections import defaultdict
from datetime import datetime

from django.db.models import F
from django.utils import timezone

from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
)
from eveonline.models.characters import EvePlayer
from fleets.models import EveFleetInstanceMember
from tribes.models import TribeGroupRequirementAssetType
from tribes.reports.roster import roster_character_eve_ids, roster_user_ids
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = [
    "primary_character_name",
    "kill_count",
    "fleet_count",
    "loss_count",
]


def _qualifying_ship_type_ids(tribe_group) -> list[int]:
    return list(
        TribeGroupRequirementAssetType.objects.filter(
            requirement__tribe_group=tribe_group,
            eve_type_id__isnull=False,
        )
        .values_list("eve_type_id", flat=True)
        .distinct()
    )


def run_capitals_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    ship_type_ids = _qualifying_ship_type_ids(tribe_group)
    if not ship_type_ids:
        return [], {"note": "No qualifying ship types configured"}, COLUMNS

    start_dt = timezone.make_aware(
        datetime.combine(period.start, datetime.min.time())
    )
    end_dt = timezone.make_aware(
        datetime.combine(period.end, datetime.max.time())
    )

    if scope == ReportScope.ROSTER:
        char_eve_ids = roster_character_eve_ids(tribe_group)
        user_ids = roster_user_ids(tribe_group)
        if not char_eve_ids:
            return [], _empty_totals(), COLUMNS
    else:
        char_eve_ids = None
        user_ids = None

    kills_by_user = _kill_counts(ship_type_ids, start_dt, end_dt, char_eve_ids)
    losses_by_user = _loss_counts(
        ship_type_ids, start_dt, end_dt, char_eve_ids
    )
    fleets_by_user = _fleet_counts(
        ship_type_ids, start_dt, end_dt, char_eve_ids
    )

    if scope == ReportScope.ROSTER:
        all_user_ids = user_ids
    else:
        all_user_ids = (
            set(kills_by_user.keys())
            | set(losses_by_user.keys())
            | set(fleets_by_user.keys())
        )

    rows = _build_rows(
        all_user_ids, kills_by_user, losses_by_user, fleets_by_user
    )
    totals = {
        "total_kills": sum(kills_by_user.values()),
        "total_losses": sum(losses_by_user.values()),
        "total_fleets": sum(fleets_by_user.values()),
    }
    return rows, totals, COLUMNS


def _kill_counts(ship_type_ids, start_dt, end_dt, char_eve_ids):
    """Attacker kills while flying a qualifying ship (excludes victim-side rows)."""
    kills_by_user: dict[int, int] = defaultdict(int)

    attacker_qs = (
        EveCharacterKillmailAttacker.objects.filter(
            ship_type_id__in=ship_type_ids,
            killmail__killmail_time__gte=start_dt,
            killmail__killmail_time__lte=end_dt,
        )
        .exclude(character_id=F("killmail__victim_character_id"))
        .select_related("killmail")
    )

    if char_eve_ids is not None:
        attacker_qs = attacker_qs.filter(character_id__in=char_eve_ids)

    char_eve_ids_seen = {
        att.character_id
        for att in attacker_qs.iterator()
        if att.character_id is not None
    }
    char_to_user = _char_eve_id_to_user(char_eve_ids_seen)

    for att in attacker_qs.iterator():
        if att.character_id is None:
            continue
        user_id = char_to_user.get(att.character_id)
        if user_id:
            kills_by_user[user_id] += 1

    return kills_by_user


def _loss_counts(ship_type_ids, start_dt, end_dt, char_eve_ids):
    """Losses of qualifying hulls; member is the killmail victim (matches lossmail ingest)."""
    losses_by_user: dict[int, int] = defaultdict(int)

    loss_qs = EveCharacterKillmail.objects.filter(
        ship_type_id__in=ship_type_ids,
        killmail_time__gte=start_dt,
        killmail_time__lte=end_dt,
        victim_character_id=F("character__character_id"),
    ).select_related("character")

    if char_eve_ids is not None:
        loss_qs = loss_qs.filter(character__character_id__in=char_eve_ids)
    else:
        loss_qs = loss_qs.filter(character__user_id__isnull=False)

    for killmail in loss_qs.iterator():
        if not killmail.character or not killmail.character.user_id:
            continue
        losses_by_user[killmail.character.user_id] += 1

    return losses_by_user


def _fleet_counts(ship_type_ids, start_dt, end_dt, char_eve_ids):
    fleets_by_user: dict[int, int] = defaultdict(int)

    qs = EveFleetInstanceMember.objects.filter(
        ship_type_id__in=ship_type_ids,
        join_time__gte=start_dt,
        join_time__lte=end_dt,
    )
    if char_eve_ids is not None:
        qs = qs.filter(character_id__in=char_eve_ids)

    char_eve_ids_seen = set(qs.values_list("character_id", flat=True))
    char_to_user = _char_eve_id_to_user(char_eve_ids_seen)

    for member in qs.iterator():
        user_id = char_to_user.get(member.character_id)
        if user_id:
            fleets_by_user[user_id] += 1

    return fleets_by_user


def _char_eve_id_to_user(char_eve_ids):
    if not char_eve_ids:
        return {}
    return {
        c.character_id: c.user_id
        for c in EveCharacter.objects.filter(
            character_id__in=char_eve_ids,
            user_id__isnull=False,
        ).only("character_id", "user_id")
    }


def _build_rows(user_ids, kills_by_user, losses_by_user, fleets_by_user):
    players = {
        p.user_id: p
        for p in EvePlayer.objects.filter(user_id__in=user_ids).select_related(
            "primary_character"
        )
    }
    rows = []
    for uid in user_ids:
        player = players.get(uid)
        name = ""
        if player and player.primary_character:
            name = player.primary_character.character_name or ""
        rows.append(
            {
                "primary_character_name": name,
                "kill_count": kills_by_user.get(uid, 0),
                "fleet_count": fleets_by_user.get(uid, 0),
                "loss_count": losses_by_user.get(uid, 0),
            }
        )
    rows.sort(
        key=lambda r: (r["kill_count"], r["fleet_count"], -r["loss_count"]),
        reverse=True,
    )
    return rows


def _empty_totals():
    return {"total_kills": 0, "total_losses": 0, "total_fleets": 0}
