"""Tie campaign fleets to the pilots who flew them and the kills they got.

A fleet counts for a campaign when someone set `campaign` on it. Attendance
comes from the fleet instance members the existing ESI poller already writes,
so campaigns add no polling of their own.
"""

from __future__ import annotations

import logging

from django.db.models import Q

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

    ESI reports when a pilot joined a fleet but never when they left. The
    fleet poller rewrites a member row every pass while that pilot is still
    in the fleet, so ``updated_at`` is the last moment we actually saw them
    and ``[join_time, updated_at]`` is the window they were present for. A
    standing fleet stays open for days, so bounding by the fleet's lifetime
    instead would credit someone who joined once and logged off for every
    day after.
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
        fleet = member.eve_fleet_instance.eve_fleet
        window = _presence_window(member, start, end)
        if window is None:
            continue

        present_from, present_to = window
        user = roster.user_for(member.character_id, present_from)
        if user is None:
            continue

        row = row_for(user.id)
        row["attended"].add(fleet.id)
        if member.solar_system_id in primary_system_ids:
            row["attended_primary"].add(fleet.id)
        if fleet.type == STANDING_FLEET_TYPE:
            row["standing_day"] = True
            row["standing_minutes"] += int(
                (present_to - present_from).total_seconds() // 60
            )

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


def _presence_window(member, start, end):
    """When this pilot was in the fleet, clipped to the campaign day.

    The poller rewrites the row on every pass, so ``updated_at`` is the last
    time we actually saw them. Returns None when that window does not reach
    into the day at all. A pilot seen by a single poll gets the attendance
    but no minutes, which is exactly what we know.
    """
    joined_at = member.join_time
    last_seen = member.updated_at or joined_at
    instance = member.eve_fleet_instance
    if instance.end_time:
        last_seen = min(last_seen, instance.end_time)
    last_seen = max(last_seen, joined_at)

    if last_seen < start or joined_at >= end:
        return None

    return max(joined_at, start), min(last_seen, end)


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
