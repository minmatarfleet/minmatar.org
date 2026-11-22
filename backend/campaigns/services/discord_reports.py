"""Structures and timers reported with a Discord command.

The bot calls in with the server the command ran in and the reporter's
Discord id. A server reports to the campaigns it coordinates or is linked
to. The reporter needs the campaign's Recon or Coordinator role (matched on
the Discord id, so allies without a site account can report) or, with a
linked site account, the same rights the website's recon form asks for.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from campaigns.constants import STRUCTURE_TYPE_IDS
from campaigns.models import (
    Campaign,
    CampaignRoleKind,
    CampaignRoleMember,
    CampaignStatus,
    StructureStatus,
)
from campaigns.services import structures as structure_service
from discord.models import DiscordUser
from structures.models import EveStructureTimer

# Campaigns a command can report to: not drafts, not finished.
REPORTING_STATUSES = (
    CampaignStatus.SCHEDULED,
    CampaignStatus.ACTIVE,
    CampaignStatus.PAUSED,
)
REPORTING_ROLES = (CampaignRoleKind.COORDINATOR, CampaignRoleKind.RECON)
TIMER_STATES = {choice[0] for choice in EveStructureTimer.state_choices}

# A timer up to this long ago is still taken: the fight may be on now.
PAST_GRACE = dt.timedelta(hours=1)

_SYSTEM_AND_NAME = re.compile(r"^\s*(.+?) - (.+?)\s*$")
_SKYHOOK = re.compile(r"^\s*(.+?) \((.+?)\)(?: \[(.*)\])?\s*$")
_UNTIL = re.compile(r" until (\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})")
_PLANET = re.compile(r"\s+[IVXLC]+$")


class ReportError(Exception):
    """A message for the reporter."""


@dataclass
class Placement:
    system_name: str
    name: str
    owner: str = ""


def campaigns_for_guild(guild_id: int):
    """Live campaigns run from or linked to this server."""
    query = Q(coordination_guild_id=guild_id) | Q(
        discord_links__guild_id=guild_id
    )
    if guild_id == int(settings.DISCORD_GUILD_ID or 0):
        # Ours is the coordination server of a campaign that names none.
        query |= Q(coordination_guild_id__isnull=True)
    return (
        Campaign.objects.filter(query, status__in=REPORTING_STATUSES)
        .distinct()
        .order_by("-start_at", "name")
    )


def _site_user(discord_user_id: int):
    linked = (
        DiscordUser.objects.select_related("user")
        .filter(id=discord_user_id)
        .first()
    )
    return linked.user if linked else None


def reporter(campaign: Campaign, discord_user_id: int):
    """(may report, site user or None) for this Discord user."""
    user = _site_user(discord_user_id)
    holds_role = CampaignRoleMember.objects.filter(
        role__campaign=campaign,
        role__kind__in=REPORTING_ROLES,
        discord_user_id=discord_user_id,
    ).first()
    if holds_role is not None:
        return True, user or holds_role.user
    if user is None:
        return False, None
    # pylint: disable-next=import-outside-toplevel
    from campaigns.endpoints.manage import _can_scout

    return _can_scout(user, campaign), user


def reportable_campaigns(guild_id: int, discord_user_id: int) -> list:
    return [
        campaign
        for campaign in campaigns_for_guild(guild_id)
        if reporter(campaign, discord_user_id)[0]
    ]


def pick_campaign(
    guild_id: int, discord_user_id: int, slug: str = ""
) -> tuple[Campaign, object]:
    """The campaign this report goes to and the reporter's site user."""
    campaigns = list(campaigns_for_guild(guild_id))
    if not campaigns:
        raise ReportError("This server isn't running a campaign.")
    if slug:
        campaigns = [c for c in campaigns if slug in (c.slug, c.short_code)]
        if not campaigns:
            raise ReportError("This server doesn't run that campaign.")
    allowed = [
        (campaign, user)
        for campaign in campaigns
        for ok, user in [reporter(campaign, discord_user_id)]
        if ok
    ]
    if not allowed:
        raise ReportError(
            "Only the campaign's Recon and Coordinators can report. "
            "Ask a coordinator for the Recon role."
        )
    if len(allowed) > 1:
        names = ", ".join(campaign.name for campaign, _ in allowed)
        raise ReportError(
            f"This server runs more than one campaign ({names}). "
            "Pick one in the command's campaign option."
        )
    return allowed[0]


def _system_from_location(location: str) -> str:
    """A skyhook sits at a planet ("KBP7-G III"); its system is the rest."""
    return _PLANET.sub("", location.strip())


def parse_placement(text: str, structure_type: str) -> Placement:
    """System and name from the first line of the selected item window."""
    first = next(
        (line for line in (text or "").splitlines() if line.strip()), ""
    )
    if structure_type == "orbital_skyhook":
        match = _SKYHOOK.match(first)
        if match:
            return Placement(
                system_name=_system_from_location(match.group(2)),
                name=match.group(1).strip(),
                owner=(match.group(3) or "").strip(),
            )
    match = _SYSTEM_AND_NAME.match(first)
    if not match:
        raise ReportError(
            "Paste the selected item window, starting with the "
            '"System - Structure name" line.'
        )
    return Placement(
        system_name=match.group(1).strip(), name=match.group(2).strip()
    )


def parse_timer(text: str, now=None) -> dt.datetime:
    match = _UNTIL.search(text or "")
    if not match:
        raise ReportError(
            'No timer found. The paste needs the "... until '
            'YYYY.MM.DD HH:MM:SS" line.'
        )
    at = dt.datetime.strptime(match.group(1), "%Y.%m.%d %H:%M:%S").replace(
        tzinfo=dt.timezone.utc
    )
    if at < (now or timezone.now()) - PAST_GRACE:
        raise ReportError("That timer has already passed.")
    return at


def _check_type(structure_type: str) -> None:
    if structure_type not in STRUCTURE_TYPE_IDS:
        raise ReportError("Pick a structure type from the list.")


def report_timer(
    campaign: Campaign,
    user,
    *,
    structure_type: str,
    state: str,
    selected_item_window: str,
    corporation_name: str = "",
    alliance_name: str = "",
):
    _check_type(structure_type)
    if state not in TIMER_STATES:
        raise ReportError("Pick a timer state from the list.")
    placement = parse_placement(selected_item_window, structure_type)
    at = parse_timer(selected_item_window)
    corporation_name = corporation_name.strip() or placement.owner
    timer = EveStructureTimer.objects.create(
        name=placement.name,
        state=state,
        type=structure_type,
        timer=at,
        created_by=user,
        corporation_name=corporation_name or None,
        alliance_name=alliance_name.strip() or None,
        system_name=placement.system_name,
        campaign=campaign,
    )
    try:
        structure_service.attach_timer(campaign, timer, created_by=user)
    except ValueError as exc:
        timer.delete()
        raise ReportError(_unknown_system(placement, exc)) from exc
    return timer


def report_structure(
    campaign: Campaign,
    user,
    *,
    structure_type: str,
    selected_item_window: str,
    corporation_name: str = "",
    alliance_name: str = "",
    reinforce_hour: int | None = None,
):
    _check_type(structure_type)
    if reinforce_hour is not None and not 0 <= reinforce_hour <= 23:
        raise ReportError("The reinforcement hour is 0 to 23, in EVE time.")
    placement = parse_placement(selected_item_window, structure_type)
    try:
        return structure_service.attach_structure(
            campaign,
            name=placement.name,
            structure_type=structure_type,
            system_name=placement.system_name,
            corporation_name=corporation_name.strip() or placement.owner,
            alliance_name=alliance_name.strip(),
            status=StructureStatus.ANCHORED,
            created_by=user,
            reinforce_hour=reinforce_hour,
        )
    except ValueError as exc:
        raise ReportError(_unknown_system(placement, exc)) from exc


def _unknown_system(placement: Placement, exc: ValueError) -> str:
    if "unknown solar system" in str(exc):
        return f'We don\'t know the system "{placement.system_name}".'
    return str(exc)
