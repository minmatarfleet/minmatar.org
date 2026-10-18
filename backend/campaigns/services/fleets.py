"""Tie campaign fleets to the pilots who flew them and the kills they got.

A fleet counts for a campaign when someone set `campaign` on it. Attendance
comes from the fleet instance members the existing ESI poller already writes,
so campaigns add no polling of their own.
"""

from __future__ import annotations

import logging

from django.db.models import Q

from campaigns.helpers import CampaignRoster, day_bounds
from campaigns.models import Campaign, CampaignKillmail
from fleets.helpers.presence import member_window, was_present
from fleets.models import EveFleetInstance, EveFleetInstanceMember

logger = logging.getLogger(__name__)

STANDING_FLEET_TYPE = "standing"
GANG_FLEET_TYPE = "gang"


def _instances_overlapping(campaign: Campaign, start, end):
    """Fleet instances of this campaign that were up during a window."""
    return EveFleetInstance.objects.filter(
        eve_fleet__campaign=campaign, start_time__lt=end
    ).filter(Q(end_time__isnull=True) | Q(end_time__gt=start))


def _credit_fleet_leaders(instances, row_for) -> None:
    """The pilot who created a fleet led it; a gang they formed counts too."""
    for instance in instances:
        fleet = instance.eve_fleet
        if not fleet.created_by_id:
            continue
        row = row_for(fleet.created_by_id)
        if fleet.type == GANG_FLEET_TYPE:
            row["gangs_led"].add(fleet.id)
            row["gangs"].add(fleet.id)
        elif fleet.type != STANDING_FLEET_TYPE:
            row["led"].add(fleet.id)


def attendance_for_day(campaign: Campaign, day) -> dict[int, dict]:
    """Per-pilot fleet activity for one campaign day.

    Returns ``{user_id: {attended, attended_primary, led, gangs_led, gangs,
    standing_minutes, standing_day}}``. ``gangs`` is the gang fleets a pilot
    formed or joined. A pilot counts once per fleet,
    however many times they rejoined it.

    ESI reports when a pilot joined a fleet but never when they left, so
    presence is the member's window from fleets.helpers.presence: first
    seen to last seen. A standing fleet stays open for days, so bounding by
    the fleet's lifetime instead would credit someone who joined once and
    logged off for every day after.

    Units: ``attended`` counts distinct scheduled fleets (EveFleet) for the
    day, so a multi-day standing fleet is one fleet per day the pilot was in
    it. That is on purpose: each day in it earns the day's fleet points.
    ``led`` counts fleets the pilot created that had an ESI instance up that
    day, standing fleets excluded and gangs counted apart, which is why it
    differs from fleets.helpers.metrics.led_fleets.
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
                "gangs": set(),
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

    # Anyone first seen by the end of the day may have been in the fleet
    # during it; _presence_window drops those who were gone before it. ESI
    # moves join_time forward on a rejoin, so it alone would lose the days
    # before the rejoin.
    members = (
        EveFleetInstanceMember.objects.filter(eve_fleet_instance__in=instances)
        .filter(Q(join_time__lt=end) | Q(created_at__lt=end))
        .select_related("eve_fleet_instance__eve_fleet")
    )

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
        if fleet.type == GANG_FLEET_TYPE:
            row["gangs"].add(fleet.id)
        if fleet.type == STANDING_FLEET_TYPE:
            row["standing_day"] = True
            row["standing_minutes"] += int(
                (present_to - present_from).total_seconds() // 60
            )

    _credit_fleet_leaders(instances, row_for)

    return {
        user_id: {
            "attended": len(values["attended"]),
            "attended_primary": len(values["attended_primary"]),
            "led": len(values["led"]),
            "gangs_led": len(values["gangs_led"]),
            "gangs": len(values["gangs"]),
            "standing_minutes": values["standing_minutes"],
            "standing_day": values["standing_day"],
        }
        for user_id, values in rows.items()
    }


def fleet_ids_by_user(campaign: Campaign, since=None) -> dict[int, set[int]]:
    """Every campaign fleet each pilot was in, optionally since a moment.

    For pooling pilots (a corporation's row), where thirty members in one
    fleet is one fleet. A pilot counts for the fleet if one of their
    characters counted for them at either end of its window.
    """
    roster = CampaignRoster(campaign)
    if not roster:
        return {}
    members = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance__eve_fleet__campaign=campaign
    )
    if since is not None:
        members = members.filter(updated_at__gte=since)
    fleets: dict[int, set[int]] = {}
    for row in members.values_list(
        "character_id",
        "eve_fleet_instance__eve_fleet_id",
        "join_time",
        "created_at",
        "updated_at",
    ):
        character_id, fleet_id = row[0], row[1]
        first_seen, last_seen = member_window(*row[2:])
        user = roster.user_for(character_id, first_seen) or roster.user_for(
            character_id, last_seen
        )
        if user is not None:
            fleets.setdefault(user.id, set()).add(fleet_id)
    return fleets


def _presence_window(member, start, end):
    """When this pilot was in the fleet, clipped to the campaign day.

    Returns None when the member's window does not reach into the day at
    all. A pilot seen by a single poll gets the attendance but no minutes,
    which is exactly what we know. A pilot who dropped and rejoined is
    counted for the gap too: the poller cannot see it.
    """
    joined_at, last_seen = member_window(
        member.join_time, member.created_at, member.updated_at
    )
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
            (
                member.eve_fleet_instance,
                member_window(
                    member.join_time, member.created_at, member.updated_at
                ),
            )
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
    """The fleet a pilot on the mail was in when it happened, if any.

    The pilot's own window decides, as on the fleet page's kill card: a
    standing fleet stays open for days, so being in it once is not being in
    it for every kill after.
    """
    for participant in mail.participants.all():
        for instance, window in membership.get(participant.character_id, []):
            if instance.start_time > mail.killmail_time:
                continue
            if instance.end_time and instance.end_time < mail.killmail_time:
                continue
            if not was_present(window, mail.killmail_time):
                continue
            return instance.eve_fleet_id
    return None
