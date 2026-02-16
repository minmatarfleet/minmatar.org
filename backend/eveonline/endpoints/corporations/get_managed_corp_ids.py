"""GET /managed - get IDs of corporations the current user can manage."""

from typing import List

from ninja import Router

from authentication import AuthBearer
from eveonline.models import EveCorporation
from groups.helpers import PEOPLE_TEAM, TECH_TEAM, user_in_team

router = Router(tags=["Corporations"])

FL33T_ID = 99011978
BUILD_ID = 99012009


@router.get(
    "managed",
    response=List[int],
    auth=AuthBearer(),
    summary="Get IDs of corporations the current user can manage",
)
def get_managed_corp_ids(request) -> List[int]:
    user = request.user
    team_access = user_in_team(user, PEOPLE_TEAM) or user_in_team(
        user, TECH_TEAM
    )
    corporations = EveCorporation.objects.filter(
        alliance__alliance_id__in=(FL33T_ID, BUILD_ID)
    ).prefetch_related("ceo__token__user")
    response = []
    for corp in corporations:
        if team_access:
            response.append(corp.corporation_id)
        elif corp.ceo and corp.ceo.token and corp.ceo.token.user == user:
            response.append(corp.corporation_id)
    return response
