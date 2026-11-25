"""POST /corporations/{corporation_id}/members/{character_id}/status

Puts a member on leave, makes them alumni, or restores them to active from
the corp Members tab. Same rules as the alliance health lists: the corp's CEO
(or a superuser) puts people on leave and makes them alumni, with a write-up
that is sent to the pilot; the CEO, directors and the People team take them
off leave; only the CEO or a superuser takes someone off alumni.
"""

from typing import Literal

from ninja import Router, Schema

from alliance.helpers.status_change import change_community_status
from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.get_corp_member_insights import (
    in_corporation,
)
from eveonline.helpers.corporations.permissions import (
    can_view_corporation_members,
)
from eveonline.helpers.corporations.profile import load_corporation
from eveonline.models import EveCharacter

router = Router(tags=["Corporations"])


class CorporationMemberStatusRequest(Schema):
    action: Literal["leave", "alumni", "restore"]
    # Required for alumni: why they are alumni, sent to them on Discord.
    reason: str = ""


class CorporationMemberStatusResponse(Schema):
    community_status: str


@router.post(
    "corporations/{corporation_id}/members/{character_id}/status",
    response={
        200: CorporationMemberStatusResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Put a member on leave, make them alumni, or restore them",
)
def post_corp_member_status(
    request,
    corporation_id: int,
    character_id: int,
    payload: CorporationMemberStatusRequest,
):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_view_corporation_members(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    character = (
        EveCharacter.objects.filter(character_id=character_id)
        .select_related("user")
        .first()
    )
    if (
        character is None
        or not character.user_id
        or not in_corporation(character, corporation_id)
    ):
        return 404, ErrorResponse(detail="Member not found")
    if payload.action == "alumni":
        reason = payload.reason
    else:
        done = "Put on leave" if payload.action == "leave" else "Restored"
        reason = f"{done} on the {corporation.ticker} Members tab"
    result = change_community_status(
        request.user, character.user, payload.action, reason
    )
    if result.error:
        return result.code, ErrorResponse(detail=result.error)
    return CorporationMemberStatusResponse(community_status=result.status)
