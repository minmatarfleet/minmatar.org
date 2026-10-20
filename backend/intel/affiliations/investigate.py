"""Read one group's zKillboard history into monthly evidence rows.

zKill's ``kills/<kind>ID/<id>/year/<y>/month/<m>/`` returns full killmails,
200 a page, newest first, so one page per month is the sample and no ESI
call is needed per mail. A month that had ended when it was read is never
read again (killmails don't change), so a re-investigation costs about two
months: the current one and the one before it.
"""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

import requests
from django.db import transaction
from django.utils import timezone

from eveonline.client import EsiClient
from feed.helpers.zkill_client import ZKILL_API_BASE, zkill_get
from intel.affiliations.names import esi_names
from intel.affiliations.constants import (
    FIRST_PLAYER_CORPORATION_ID,
    MAX_ATTACKERS,
    MIN_SHARED_ROW,
    WINDOW_MONTHS,
    ZKILL_SLEEP_SECONDS,
)
from intel.models import IntelCoAttack, IntelEntity, IntelSampleMonth

logger = logging.getLogger(__name__)

ALLIANCE = IntelEntity.Kind.ALLIANCE
CORPORATION = IntelEntity.Kind.CORPORATION
CHARACTER = IntelEntity.Kind.CHARACTER


class ZkillUnavailable(Exception):
    """zKill didn't answer; the months read so far are kept."""


def month_starts(today: date, count: int = WINDOW_MONTHS) -> list[date]:
    """The first day of this month and the ``count - 1`` before it."""
    year, month = today.year, today.month
    months = []
    for _ in range(count):
        months.append(date(year, month, 1))
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return months


def group_of(entity: dict) -> tuple[str, int] | None:
    """The group a killmail attacker or victim flew for, if a player group."""
    if entity.get("alliance_id"):
        return ALLIANCE, int(entity["alliance_id"])
    corporation_id = entity.get("corporation_id")
    if corporation_id and corporation_id >= FIRST_PLAYER_CORPORATION_ID:
        return CORPORATION, int(corporation_id)
    return None


@dataclass
class MonthCount:
    """One month of a group's sample, before it is written."""

    kills: int = 0
    losses: int = 0
    shared: Counter = field(default_factory=Counter)
    militia_shared: Counter = field(default_factory=Counter)
    against: Counter = field(default_factory=Counter)
    # character_id -> the group they flew for on their latest shared kill
    character_groups: dict = field(default_factory=dict)
    factions: Counter = field(default_factory=Counter)


def is_subject(entity: dict, subject: tuple[str, int]) -> bool:
    """An attacker or victim flying for the group being investigated.

    A corporation inside an alliance is matched by its own id, not by the
    alliance its pilots show as their group.
    """
    kind, eve_id = subject
    return entity.get(f"{kind}_id") == eve_id


def _count_kill(count: MonthCount, subject, attackers: list[dict]) -> None:
    ours = [a for a in attackers if is_subject(a, subject)]
    if not ours:
        return
    count.kills += 1
    our_factions = {a.get("faction_id") for a in ours} - {None}
    count.factions.update(our_factions)
    # A corporation's own alliance (and its pilots) are not partners.
    own = {group_of(a) for a in ours}
    partners: dict[tuple[str, int], bool] = {}
    for attacker in attackers:
        group = group_of(attacker)
        if is_subject(attacker, subject) or group in own:
            continue
        militia = attacker.get("faction_id") in our_factions
        keys = [group] if group else []
        if attacker.get("character_id"):
            character_id = int(attacker["character_id"])
            keys.append((CHARACTER, character_id))
            count.character_groups[character_id] = group[1] if group else None
        for key in keys:
            partners[key] = partners.get(key, False) or militia
    for partner, militia in partners.items():
        count.shared[partner] += 1
        count.militia_shared[partner] += militia


def count_month(
    subject: tuple[str, int], kills: list[dict], losses: list[dict]
) -> MonthCount:
    """Who flew with ``subject`` on its kills, and who shot its losses."""
    count = MonthCount()
    for mail in kills:
        attackers = mail.get("attackers") or []
        if len(attackers) <= MAX_ATTACKERS:
            _count_kill(count, subject, attackers)
    for mail in losses:
        victim = mail.get("victim") or {}
        if not is_subject(victim, subject):
            continue
        count.losses += 1
        shooters = {
            group_of(attacker) for attacker in mail.get("attackers") or []
        }
        for group in shooters - {None, subject, group_of(victim)}:
            count.against[group] += 1
    return count


def _rows(entity: IntelEntity, month: date, count: MonthCount) -> list:
    keys = set(count.shared) | set(count.against)
    rows = []
    for kind, partner_id in keys:
        shared = count.shared.get((kind, partner_id), 0)
        against = count.against.get((kind, partner_id), 0)
        if shared < MIN_SHARED_ROW and not against:
            continue
        rows.append(
            IntelCoAttack(
                entity=entity,
                month=month,
                partner_kind=kind,
                partner_id=partner_id,
                partner_group=(
                    count.character_groups.get(partner_id)
                    if kind == CHARACTER
                    else None
                ),
                shared=shared,
                militia_shared=count.militia_shared.get((kind, partner_id), 0),
                against=against,
            )
        )
    return rows


def _fetch(path: str) -> list[dict]:
    try:
        response = zkill_get(f"{ZKILL_API_BASE}/{path}/")
        response.raise_for_status()
        entries = response.json()
    except (requests.RequestException, ValueError) as error:
        raise ZkillUnavailable(path) from error
    return entries if isinstance(entries, list) else []


def fetch_month(kind: str, eve_id: int, month: date, sleep_seconds: float):
    """One page of kills and one of losses for the month."""
    path = f"{kind}ID/{eve_id}/year/{month.year}/month/{month.month}/page/1"
    kills = _fetch(f"kills/{path}")
    time.sleep(sleep_seconds)
    losses = _fetch(f"losses/{path}")
    time.sleep(sleep_seconds)
    return kills, losses


def _refresh_profile(entity: IntelEntity, factions: Counter) -> None:
    # From ESI, not our row: groups rename.
    names = esi_names([entity.eve_id])
    if names.get(entity.eve_id):
        entity.name = names[entity.eve_id]
    entity.faction_id = factions.most_common(1)[0][0] if factions else None
    if entity.kind == CORPORATION:
        response = EsiClient(None).get_corporation_alliance_history(
            entity.eve_id
        )
        if response.success():
            entity.alliance_history = [
                {
                    "alliance_id": row.get("alliance_id"),
                    "start_date": str(row.get("start_date") or "")[:10],
                }
                for row in response.results() or []
            ]


def investigate(
    entity: IntelEntity,
    *,
    today: date | None = None,
    sleep_seconds: float = ZKILL_SLEEP_SECONDS,
) -> dict:
    """Read the group's unread months and record the evidence."""
    today = today or timezone.now().date()
    months = month_starts(today)
    complete = set(
        IntelSampleMonth.objects.filter(
            entity=entity, complete=True, month__in=months
        ).values_list("month", flat=True)
    )
    IntelEntity.objects.filter(pk=entity.pk).update(
        status=IntelEntity.Status.INVESTIGATING
    )
    subject = (entity.kind, entity.eve_id)
    factions: Counter = Counter()
    stats: dict = defaultdict(int)
    try:
        for month in months:
            if month in complete:
                stats["skipped"] += 1
                continue
            kills, losses = fetch_month(
                entity.kind, entity.eve_id, month, sleep_seconds
            )
            count = count_month(subject, kills, losses)
            factions.update(count.factions)
            with transaction.atomic():
                IntelCoAttack.objects.filter(
                    entity=entity, month=month
                ).delete()
                IntelCoAttack.objects.bulk_create(_rows(entity, month, count))
                IntelSampleMonth.objects.update_or_create(
                    entity=entity,
                    month=month,
                    defaults={
                        "kills": count.kills,
                        "losses": count.losses,
                        "complete": month < months[0],
                    },
                )
            stats["months"] += 1
            stats["kills"] += count.kills
    except ZkillUnavailable:
        logger.warning("zKill unavailable investigating %s", entity)
        entity.status = IntelEntity.Status.FAILED
        entity.save(update_fields=["status", "updated_at"])
        stats["failed"] = 1
        return dict(stats)
    if not factions:
        # Every month was already read; keep the militia we knew.
        factions = Counter({entity.faction_id: 1} if entity.faction_id else {})
    _refresh_profile(entity, factions)
    entity.status = IntelEntity.Status.DONE
    entity.investigated_at = timezone.now()
    entity.priority = 0
    entity.save()
    return dict(stats)
