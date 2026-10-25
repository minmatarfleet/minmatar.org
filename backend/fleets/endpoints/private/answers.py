"""A pilot's answer to a fleet invite, from the fleet page or the invite
DM's buttons: Sitting out, I'm in with no ship yet, and Stop fleet invites.

I'm in with ships is volunteering through the existing picker endpoints;
the volunteer signals mark the invite answered (fleets/signals.py).
"""

from app.errors import ErrorResponse
from authentication import AuthBearer, is_service_account
from discord.models import DiscordUser
from fleets.endpoints.private.schemas import (
    DiscordSitOutRequest,
    MyInviteResponse,
    StopInvitesResponse,
)
from fleets.helpers.private_fleets import (
    PrivateFleetError,
    say_in,
    sit_out,
    stop_fleet_invites,
)
from fleets.models import EveFleetInvite


def _sit_out(invite):
    try:
        sit_out(invite)
    except PrivateFleetError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    return 200, MyInviteResponse(invite_id=invite.id, answer=invite.answer)


def _my_invite(request, fleet_id: int):
    return (
        EveFleetInvite.objects.select_related("eve_fleet")
        .filter(eve_fleet_id=fleet_id, user_id=request.user.pk)
        .first()
    )


def post_my_invite_out(request, fleet_id: int):
    invite = _my_invite(request, fleet_id)
    if invite is None:
        return 404, None
    return _sit_out(invite)


def post_my_invite_in(request, fleet_id: int):
    invite = _my_invite(request, fleet_id)
    if invite is None:
        return 404, None
    try:
        say_in(invite)
    except PrivateFleetError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    return 200, MyInviteResponse(invite_id=invite.id, answer=invite.answer)


def _discord_invite(request, invite_id: int, discord_user_id: int):
    """The invite if this Discord user owns it (and the caller is them or
    the bot), else an error tuple."""
    invite = (
        EveFleetInvite.objects.select_related("eve_fleet", "user")
        .filter(id=invite_id)
        .first()
    )
    if invite is None:
        return 404, ErrorResponse(detail="Invite not found.")
    discord_user = DiscordUser.objects.filter(id=discord_user_id).first()
    if discord_user is None or discord_user.user_id != invite.user_id:
        return 403, ErrorResponse(detail="This invite isn't yours.")
    if request.user.pk != invite.user_id and not is_service_account(
        request.user
    ):
        return 403, ErrorResponse(detail="This invite isn't yours.")
    return invite


def post_invite_discord_out(
    request, invite_id: int, payload: DiscordSitOutRequest
):
    """The bot, on behalf of the Discord user who pressed Sitting out."""
    invite = _discord_invite(request, invite_id, payload.discord_user_id)
    if isinstance(invite, tuple):
        return invite
    return _sit_out(invite)


def post_invite_discord_stop(
    request, invite_id: int, payload: DiscordSitOutRequest
):
    """The bot, on behalf of the Discord user who pressed Stop fleet
    invites: no more standard fleet invite DMs."""
    invite = _discord_invite(request, invite_id, payload.discord_user_id)
    if isinstance(invite, tuple):
        return invite
    stop_fleet_invites(invite.user)
    return 200, StopInvitesResponse(stopped=True)


_RESPONSES = {
    200: MyInviteResponse,
    400: ErrorResponse,
    403: ErrorResponse,
    404: ErrorResponse,
}

ROUTES = (
    (
        "post",
        "/{fleet_id}/invites/me/out",
        {
            "auth": AuthBearer(),
            "response": {**_RESPONSES, 404: None},
            "description": (
                "Sit out a fleet you were invited to: clears your ships on "
                "it. You can still say I'm in until it starts."
            ),
        },
        post_my_invite_out,
    ),
    (
        "post",
        "/{fleet_id}/invites/me/in",
        {
            "auth": AuthBearer(),
            "response": {**_RESPONSES, 404: None},
            "description": (
                "Say I'm in to a fleet you were invited to without picking "
                "a ship yet. Picking ships says I'm in too."
            ),
        },
        post_my_invite_in,
    ),
    (
        "post",
        "/invites/{invite_id}/discord-out",
        {
            "auth": AuthBearer(),
            "response": _RESPONSES,
            "description": "Sitting out from the invite DM's button (bot).",
        },
        post_invite_discord_out,
    ),
    (
        "post",
        "/invites/{invite_id}/discord-stop",
        {
            "auth": AuthBearer(),
            "response": {
                200: StopInvitesResponse,
                403: ErrorResponse,
                404: ErrorResponse,
            },
            "description": (
                "Stop fleet invites from the invite DM's button (bot): turns "
                "off standard fleet invite DMs for this pilot."
            ),
        },
        post_invite_discord_stop,
    ),
)
