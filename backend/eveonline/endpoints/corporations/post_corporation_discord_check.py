"""POST /corporations/{corporation_id}/discord/check - preview an invite."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import (
    CorporationDiscordInvitePreview,
    CorporationDiscordInviteRequest,
)
from eveonline.helpers.corporations.discord_invite import (
    DiscordInviteError,
    invite_preview,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord/check"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        200: CorporationDiscordInvitePreview,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Check a Discord invite before saving it (CEO and directors)",
}


def post_corporation_discord_check(
    request, corporation_id: int, payload: CorporationDiscordInviteRequest
):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    try:
        return invite_preview(payload.invite_url)
    except DiscordInviteError as e:
        return 400, ErrorResponse(detail=e.code)
