"""GET "/external-guild/seat" — current user's seat for a tribe group."""

from django.conf import settings
from ninja import Router, Schema

from authentication import AuthBearer
from tribes.helpers.external_guild import (
    binding_for_group,
    seat_for_user_group,
)

PATH = "/external-guild/seat"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Current user's seat on a tribe group's external Discord guild.",
    "response": {200: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - External Guild"])


class ExternalGuildSeatSchema(Schema):
    binding_id: int
    group_id: int
    guild_id: int
    guild_name: str
    status: str
    oauth_join_available: bool


def get_external_guild_seat(request, group_id: int):
    binding = binding_for_group(group_id)
    if binding is None:
        return 404, {"detail": "No external Discord guild for this group."}
    seat = seat_for_user_group(request.user, group_id)
    if seat is None:
        return 404, {"detail": "No external guild seat for this user."}

    return 200, ExternalGuildSeatSchema(
        binding_id=binding.pk,
        group_id=binding.tribe_group_id,
        guild_id=binding.guild.guild_id,
        guild_name=binding.guild.name,
        status=seat.status,
        oauth_join_available=bool(
            getattr(settings, "DISCORD_EXTERNAL_GUILD_REDIRECT_URL", "")
        ),
    )


router.get(PATH, **ROUTE_SPEC)(get_external_guild_seat)
