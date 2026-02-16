"""GET /corporations/{corporation_id}/members - get corporation member details."""

from django.contrib.auth.models import User
from django.db.models import Count
from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import CorporationMemberDetails
from eveonline.models import EveCharacter, EveCorporation
from groups.helpers import PEOPLE_TEAM, TECH_TEAM, user_in_team

router = Router(tags=["Corporations"])


def _can_manage_corp_members(user: User, corporation: EveCorporation) -> bool:
    if corporation.ceo and corporation.ceo.user_id == user.id:
        return True
    if user_in_team(user, PEOPLE_TEAM):
        return True
    if user_in_team(user, TECH_TEAM):
        return True
    return False


@router.get(
    "corporations/{corporation_id}/members",
    response={200: list[CorporationMemberDetails], 403: ErrorResponse},
    auth=AuthBearer(),
    summary="Get corporation member details (leadership only)",
)
def get_corp_member_details(request, corporation_id: int):
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    if not _can_manage_corp_members(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    response = []
    members = EveCharacter.objects.filter(
        corporation_id=corporation.corporation_id
    ).annotate(token_count=Count("token"))
    for character in members:
        char = CorporationMemberDetails(
            character_id=character.character_id,
            character_name=character.character_name,
            esi_suspended=character.esi_suspended,
            exempt=character.exempt,
            token_count=character.token_count,
            token_level=character.esi_token_level or "",
        )
        if character.user:
            char.user_name = character.user.username
        response.append(char)
    return response
