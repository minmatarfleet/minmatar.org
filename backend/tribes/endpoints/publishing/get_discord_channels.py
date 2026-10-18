"""GET "/discord-channels" - the guild's text or voice channels."""

from typing import List

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints.publishing.schemas import (
    DiscordChannelKind,
    DiscordChannelSchema,
)
from tribes.helpers.discord_channels import channels_of_kind
from tribes.helpers.publishing import KIND_EVENT, publishable_groups

PATH = "/discord-channels"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Discord channels for the group channel and event pickers.",
    "description": (
        "Text channels, or voice channels (stage channels included). For "
        "anyone who can manage a group or create events for one. Cached "
        "for 10 minutes."
    ),
    "response": {200: List[DiscordChannelSchema], 403: ErrorResponse},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Publishing"])


def get_discord_channels(
    request, kind: DiscordChannelKind = DiscordChannelKind.TEXT
):
    # Managers can always publish, so this covers both.
    if not publishable_groups(request.user, KIND_EVENT):
        return 403, {
            "detail": "Only group managers and event publishers can list "
            "channels."
        }
    return 200, [
        DiscordChannelSchema(id=str(c["id"]), name=c["name"], type=c["type"])
        for c in channels_of_kind(kind.value)
    ]


router.get(PATH, **ROUTE_SPEC)(get_discord_channels)
