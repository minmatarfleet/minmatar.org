"""
Private Discord DMs for cyno system assignments.

The assigned system is deliberately kept out of the fleet MOTD and the
public API; the cyno pilot learns about it through a direct message.
"""

import logging

from django.conf import settings

from discord.client import DiscordClient
from discord.models import DiscordUser
from eveonline.models import EveCharacter

logger = logging.getLogger(__name__)


def _discord_id_for_character(character_id: int) -> str | None:
    character = (
        EveCharacter.objects.filter(character_id=character_id)
        .select_related("user")
        .first()
    )
    if not character or not character.user_id:
        return None
    discord_user = DiscordUser.objects.filter(
        user_id=character.user_id
    ).first()
    return str(discord_user.id) if discord_user else None


def _fleet_url(fleet) -> str:
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org")
    return f"{base.rstrip('/')}/fleets/upcoming/{fleet.id}"


def build_cyno_assignment_message(fleet, volunteer) -> str:
    fc = fleet.fleet_commander
    fc_name = fc.character_name if fc else "the FC"
    start = (
        fleet.start_time.strftime("%Y-%m-%d %H:%M")
        if fleet.start_time
        else "TBD"
    )
    lines = [
        f"**Cyno assignment for fleet {fleet.id}**",
        f"{fc_name} has assigned **{volunteer.character_name}** to light the cyno in "
        f"**{volunteer.solar_system_name}**.",
        f"Fleet forms up at {start} EVE. Keep this to yourself; it is not in the MOTD.",
        _fleet_url(fleet),
    ]
    return "\n".join(lines)


def build_cyno_cleared_message(fleet, volunteer) -> str:
    fc = fleet.fleet_commander
    fc_name = fc.character_name if fc else "the FC"
    return "\n".join(
        [
            f"**Cyno assignment for fleet {fleet.id}**",
            f"{fc_name} has cleared the system assignment for "
            f"**{volunteer.character_name}**. Wait for a new one.",
            _fleet_url(fleet),
        ]
    )


def notify_cyno_system_assignment(
    fleet, volunteer, cleared: bool = False
) -> bool:
    """DM the cyno volunteer's Discord account. Returns True if a DM was sent."""
    discord_id = _discord_id_for_character(volunteer.character_id)
    if not discord_id:
        logger.info(
            "Skipping cyno assignment DM for %s (no Discord link)",
            volunteer.character_name,
        )
        return False
    message = (
        build_cyno_cleared_message(fleet, volunteer)
        if cleared
        else build_cyno_assignment_message(fleet, volunteer)
    )
    try:
        DiscordClient().send_dm(discord_id, message=message)
        return True
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Failed to send cyno assignment DM to %s",
            volunteer.character_name,
            exc_info=True,
        )
        return False
