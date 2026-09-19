"""Tie campaign fleets to the pilots who flew them and the kills they got.

A fleet counts for a campaign when someone set `campaign` on it. Attendance
comes from the fleet instance members the existing ESI poller already writes,
so campaigns add no polling of their own.
"""

from __future__ import annotations

import logging
from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from campaigns.helpers import CampaignRoster, day_bounds
from campaigns.models import Campaign, CampaignKillmail, CampaignStandingFleet
from fleets.models import EveFleetInstance, EveFleetInstanceMember

logger = logging.getLogger(__name__)

STANDING_FLEET_TYPE = "standing"
GANG_FLEET_TYPE = "gang"


def _instances_overlapping(campaign: Campaign, start, end):
    """Fleet instances of this campaign that were up during a window."""
    return EveFleetInstance.objects.filter(
        eve_fleet__campaign=campaign, start_time__lt=end
    ).filter(Q(end_time__isnull=True) | Q(end_time__gt=start))


def attendance_for_day(campaign: Campaign, day) -> dict[int, dict]:
    """Per-pilot fleet activity for one campaign day.

    Returns ``{user_id: {attended, attended_primary, led, gangs_led,
    standing_minutes, standing_day}}``. A pilot counts once per fleet,
    however many times they rejoined it.

    ESI reports when a pilot joined a fleet but never when they left, so a
    day is credited whenever the fleet was up that day and the pilot had
    joined by then, and minutes are bounded by the last time the poller
    actually saw the fleet rather than assumed to run to the present.
    """
    start, end = day_bounds(day)
    roster = CampaignRoster(campaign)
    if not roster:
        return {}

    primary_system_ids = set(
        campaign.systems.filter(
            role="primary", retired_at__isnull=True
        ).values_list("solar_system_id", flat=True)
    )
    rows: dict[int, dict] = {}

    def row_for(user_id: int) -> dict:
        return rows.setdefault(
            user_id,
            {
                "attended": set(),
                "attended_primary": set(),
                "led": set(),
                "gangs_led": set(),
                "standing_minutes": 0,
                "standing_day": False,
            },
        )

    instances = list(
        _instances_overlapping(campaign, start, end).select_related(
            "eve_fleet"
        )
    )
    if not instances:
        return {}

    # Anyone who had joined by the end of the day was in the fleet during it;
    # the instance filter already limits this to fleets that were up.
    members = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance__in=instances, join_time__lt=end
    ).select_related("eve_fleet_instance__eve_fleet")

    for member in members:
        instance = member.eve_fleet_instance
        fleet = instance.eve_fleet
        seen_at = max(member.join_time, start)
        user = roster.user_for(member.character_id, seen_at)
        if user is None:
            continue

        row = row_for(user.id)
        row["attended"].add(fleet.id)
        if member.solar_system_id in primary_system_ids:
            row["attended_primary"].add(fleet.id)
        if fleet.type == STANDING_FLEET_TYPE:
            minutes = _minutes_in_window(
                member.join_time, instance, start, end
            )
            if minutes:
                row["standing_day"] = True
                row["standing_minutes"] += minutes

    for instance in instances:
        fleet = instance.eve_fleet
        if not fleet.created_by_id:
            continue
        row = row_for(fleet.created_by_id)
        if fleet.type == GANG_FLEET_TYPE:
            row["gangs_led"].add(fleet.id)
        elif fleet.type != STANDING_FLEET_TYPE:
            row["led"].add(fleet.id)

    return {
        user_id: {
            "attended": len(values["attended"]),
            "attended_primary": len(values["attended_primary"]),
            "led": len(values["led"]),
            "gangs_led": len(values["gangs_led"]),
            "standing_minutes": values["standing_minutes"],
            "standing_day": values["standing_day"],
        }
        for user_id, values in rows.items()
    }


def _minutes_in_window(joined_at: datetime, instance, start, end) -> int:
    """Minutes a pilot was in the fleet, clipped to the campaign day.

    ESI has no leave time, so the upper bound is when the fleet ended or,
    for one still open, when the poller last confirmed it existed. Using the
    present instead would credit a pilot for every minute since a fleet
    stopped being tracked.
    """
    last_known = instance.end_time or instance.last_updated or timezone.now()
    began = max(joined_at, start)
    finished = min(last_known, end)
    if finished <= began:
        return 0
    return int((finished - began).total_seconds() // 60)


def link_killmails_to_fleets(campaign: Campaign, day) -> int:
    """Attach a campaign mail to the fleet its pilots were flying in.

    A kill counts as a fleet kill when someone on the mail was in a campaign
    fleet that was up at the time. That is what earns the fleet bonus and
    what softens the penalty on a loss.
    """
    start, end = day_bounds(day)
    instances = list(
        _instances_overlapping(campaign, start, end).select_related(
            "eve_fleet"
        )
    )
    if not instances:
        return 0

    membership: dict[int, list] = {}
    for member in EveFleetInstanceMember.objects.filter(
        eve_fleet_instance__in=instances
    ).select_related("eve_fleet_instance"):
        membership.setdefault(member.character_id, []).append(
            member.eve_fleet_instance
        )

    if not membership:
        return 0

    linked = 0
    mails = CampaignKillmail.objects.filter(
        campaign=campaign,
        killmail_time__gte=start,
        killmail_time__lt=end,
        fleet__isnull=True,
    ).prefetch_related("participants")

    for mail in mails:
        fleet_id = _fleet_for_mail(mail, membership)
        if fleet_id:
            CampaignKillmail.objects.filter(id=mail.id).update(fleet=fleet_id)
            linked += 1

    return linked


def _fleet_for_mail(mail: CampaignKillmail, membership: dict):
    for participant in mail.participants.all():
        for instance in membership.get(participant.character_id, []):
            if instance.start_time > mail.killmail_time:
                continue
            if instance.end_time and instance.end_time < mail.killmail_time:
                continue
            return instance.eve_fleet_id
    return None


def refresh_standing_fleet(campaign: Campaign) -> CampaignStandingFleet | None:
    """Keep the standing-fleet card honest about who is holding it."""
    standing = getattr(campaign, "standing_fleet", None)
    if not standing or not standing.fleet_id:
        return standing

    instance = (
        EveFleetInstance.objects.filter(
            eve_fleet_id=standing.fleet_id, end_time__isnull=True
        )
        .order_by("-start_time")
        .first()
    )
    if not instance:
        standing.member_count = 0
        standing.save(update_fields=["member_count"])
        return standing

    standing.member_count = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance=instance
    ).count()
    standing.current_boss_character_id = (
        instance.boss_id or standing.current_boss_character_id
    )
    standing.last_seen_at = instance.last_updated or standing.last_seen_at
    standing.save(
        update_fields=[
            "member_count",
            "current_boss_character_id",
            "last_seen_at",
        ]
    )
    return standing
