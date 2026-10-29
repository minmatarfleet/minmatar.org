"""POST /corporations/{corporation_id}/members/{character_id}/promote

Moves a trial member to active from the corp Members tab. The CEO, directors
and the People team can do it; the status history records who.
"""

from ninja import Router, Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.get_corp_member_insights import (
    in_corporation,
)
from eveonline.helpers.corporations.permissions import (
    can_promote_corporation_trials,
)
from eveonline.helpers.corporations.profile import load_corporation
from eveonline.models import EveCharacter
from groups.helpers import promote_from_trial

router = Router(tags=["Corporations"])


class CorporationMemberPromoteResponse(Schema):
    community_status: str


@router.post(
    "corporations/{corporation_id}/members/{character_id}/promote",
    response={
        200: CorporationMemberPromoteResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Move a trial member to active (CEO, directors, People team)",
)
def post_corp_member_promote(request, corporation_id: int, character_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_promote_corporation_trials(request.user, corporation):
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
    reason = f"Promoted from trial on the {corporation.ticker} Members tab"
    if not promote_from_trial(character.user, request.user, reason):
        return 409, ErrorResponse(detail="Not on trial")
    return CorporationMemberPromoteResponse(community_status="active")
