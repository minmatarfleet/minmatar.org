"""A pilot's Sitting out, from the fleet page or the invite DM's button.

I'm in is volunteering ships through the existing picker endpoints; the
volunteer signals mark the invite answered (fleets/signals.py).
"""

from app.errors import ErrorResponse
from authentication import AuthBearer, is_service_account
from discord.models import DiscordUser
from fleets.endpoints.private.schemas import (
    DiscordSitOutRequest,
    MyInviteResponse,
)
from fleets.helpers.private_fleets import PrivateFleetError, sit_out
from fleets.models import EveFleetInvite


def _sit_out(invite):
    try:
        sit_out(invite)
    except PrivateFleetError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    return 200, MyInviteResponse(invite_id=invite.id, answer=invite.answer)


def post_my_invite_out(request, fleet_id: int):
    invite = (
        EveFleetInvite.objects.select_related("eve_fleet")
        .filter(eve_fleet_id=fleet_id, user_id=request.user.pk)
        .first()
    )
    if invite is None:
        return 404, None
    return _sit_out(invite)


def post_invite_discord_out(
    request, invite_id: int, payload: DiscordSitOutRequest
):
    """The bot, on behalf of the Discord user who pressed Sitting out."""
    invite = (
        EveFleetInvite.objects.select_related("eve_fleet")
        .filter(id=invite_id)
        .first()
    )
    if invite is None:
        return 404, ErrorResponse(detail="Invite not found.")
    discord_user = DiscordUser.objects.filter(
        id=payload.discord_user_id
    ).first()
    if discord_user is None or discord_user.user_id != invite.user_id:
        return 403, ErrorResponse(detail="This invite isn't yours.")
    if request.user.pk != invite.user_id and not is_service_account(
        request.user
    ):
        return 403, ErrorResponse(detail="This invite isn't yours.")
    return _sit_out(invite)


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
                "Sit out a private fleet you were invited to: clears your "
                "ships on it. You can still say I'm in until it starts."
            ),
        },
        post_my_invite_out,
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
)
