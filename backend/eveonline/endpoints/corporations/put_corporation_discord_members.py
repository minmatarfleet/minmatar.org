"""PUT /corporations/{corporation_id}/discord/members - who may stay."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.guild_access import AccessError, save_member_policy
from eveonline.endpoints.corporations.schemas import (
    CorporationDiscordSettings,
    DiscordMemberAccessUpdate,
)
from eveonline.helpers.corporations.discord_bot import (
    corporation_discord_settings,
    is_connected,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord/members"
METHOD = "put"
ROUTE_SPEC = {
    "response": {
        200: CorporationDiscordSettings,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": (
        "Remove people who aren't in the corporation or alliance from "
        "this corporation's Discord (CEO and directors)"
    ),
}


def _action(payload: DiscordMemberAccessUpdate) -> str | None:
    # An explicit null means "leave them"; a missing field is an older form.
    if "action" not in payload.model_fields_set:
        return None
    return payload.action or ""


def put_corporation_discord_members(
    request, corporation_id: int, payload: DiscordMemberAccessUpdate
):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    if not is_connected(corporation) or corporation.discord_guild is None:
        return 400, ErrorResponse(detail="not_connected")
    try:
        save_member_policy(
            corporation.discord_guild,
            payload.policy or "",
            payload.grace_hours,
            payload.exemptions,
            user=request.user,
            action=_action(payload),
        )
    except AccessError as error:
        return 400, ErrorResponse(detail=error.code)
    return corporation_discord_settings(corporation)
