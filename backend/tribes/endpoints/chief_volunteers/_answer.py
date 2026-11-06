"""Shared by the executor's answer endpoints (site and Discord DM)."""

from authentication import is_service_account
from discord.exceptions import DiscordRoleAssignmentError
from discord.models import DiscordUser
from tribes.endpoints.chief_volunteers.schemas import (
    ChiefVolunteerSchema,
    DiscordChiefActionRequest,
)
from tribes.endpoints.chief_volunteers.serializers import serialize_volunteer
from tribes.helpers.chiefs import ChiefVolunteerError
from tribes.models import TribeChiefVolunteer

RESPONSES = {
    200: ChiefVolunteerSchema,
    400: dict,
    403: dict,
    404: dict,
    502: dict,
}
NOT_EXECUTOR = {"detail": "Only the alliance executor appoints chiefs."}


def answer(action, volunteer_id: int, by):
    """Run ``action`` (appoint or decline) on the offer as ``by``."""
    offer = (
        TribeChiefVolunteer.objects.select_related(
            "tribe", "tribe_group", "user__eveplayer__primary_character"
        )
        .filter(pk=volunteer_id)
        .first()
    )
    if offer is None:
        return 404, {"detail": "Volunteer not found."}
    try:
        action(offer, by)
    except ChiefVolunteerError as exc:
        return exc.status_code, {"detail": str(exc)}
    except DiscordRoleAssignmentError:
        # Joining the group syncs its Discord role; a failed sync rolls the
        # appointment back, so the offer is still waiting.
        return 502, {
            "detail": "Discord didn't give them the group role, so they "
            "aren't chief yet. Try again in a minute."
        }
    return 200, serialize_volunteer(offer)


def discord_actor(request, payload: DiscordChiefActionRequest):
    """The site user behind a DM click, or None unless the bot sent it."""
    if not is_service_account(request.user):
        return None
    discord_user = (
        DiscordUser.objects.select_related("user")
        .filter(id=payload.discord_user_id)
        .first()
    )
    return discord_user.user if discord_user and discord_user.user_id else None
