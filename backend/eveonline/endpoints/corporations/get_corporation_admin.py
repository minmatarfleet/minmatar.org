"""GET /corporations/{corporation_id}/admin - leadership admin facts."""

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import CorporationAdminResponse
from eveonline.helpers.corporations.permissions import can_manage_corporation
from eveonline.helpers.corporations.profile import (
    corporation_health,
    discord_status,
    load_corporation,
)

router = Router(tags=["Corporations"])


@router.get(
    "corporations/{corporation_id}/admin",
    response={
        200: CorporationAdminResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Corporation admin facts for leadership",
)
def get_corporation_admin(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_manage_corporation(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    return {
        "corporation_id": corporation.corporation_id,
        "executor_notes": corporation.executor_notes or None,
        **discord_status(corporation),
        **corporation_health(corporation.corporation_id),
        "stewards": [
            {
                "character_id": character.character_id,
                "character_name": character.character_name,
            }
            for character in corporation.stewards.all()
        ],
    }
