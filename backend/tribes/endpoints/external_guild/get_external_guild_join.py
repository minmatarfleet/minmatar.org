"""GET "/external-guild/join" — Discord OAuth URL for tribe group external guild."""

from django.conf import settings
from ninja import Router, Schema

from authentication import AuthBearer
from discord.client import discord_authorize_url
from tribes.helpers.external_guild import (
    allowlisted_redirect_url,
    binding_for_group,
    encode_oauth_state,
    seat_for_user_group,
)
from tribes.models import TribeExternalGuildSeat

PATH = "/external-guild/join"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Discord OAuth authorize URL to join a tribe group's external guild.",
    "response": {200: dict, 400: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - External Guild"])


class ExternalGuildJoinSchema(Schema):
    authorize_url: str
    group_id: int
    status: str


def get_external_guild_join(
    request,
    group_id: int,
    redirect_url: str = "",
):
    redirect_uri = getattr(settings, "DISCORD_EXTERNAL_GUILD_REDIRECT_URL", "")
    if not redirect_uri:
        return 400, {
            "detail": "External guild OAuth is not configured "
            "(DISCORD_EXTERNAL_GUILD_REDIRECT_URL)."
        }

    binding = binding_for_group(group_id)
    if binding is None:
        return 404, {"detail": "No external Discord guild for this group."}

    seat = seat_for_user_group(request.user, group_id)
    if seat is None:
        return 404, {"detail": "No pending external guild seat for this user."}
    if seat.status not in (
        TribeExternalGuildSeat.STATUS_PENDING_JOIN,
        TribeExternalGuildSeat.STATUS_PRESENT,
    ):
        return 400, {
            "detail": f"Seat status '{seat.status}' cannot start a join."
        }

    state = encode_oauth_state(
        group_id=group_id,
        user_id=request.user.id,
        redirect_url=allowlisted_redirect_url(
            redirect_url or settings.WEB_LINK_URL
        ),
    )
    return 200, ExternalGuildJoinSchema(
        authorize_url=discord_authorize_url(
            settings.DISCORD_CLIENT_ID, redirect_uri, state=state
        ),
        group_id=group_id,
        status=seat.status,
    )


router.get(PATH, **ROUTE_SPEC)(get_external_guild_join)
