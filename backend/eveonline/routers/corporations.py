from typing import List, Optional

from ninja import Router, Schema

from authentication import AuthBearer
from eveonline.models import EveCorporation, EveAlliance

router = Router(tags=["Corporations"])


class CorporationResponse(Schema):
    corporation_id: int
    corporation_name: str
    corporation_type: str
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None


class CorporationApplicationResponse(Schema):
    status: str
    description: str
    corporation_id: int


class CreateCorporationRequest(Schema):
    corporation_id: int


@router.get(
    "/corporations",
    response=List[CorporationResponse],
    auth=AuthBearer(),
    summary="Get all corporations",
)
def get_corporations(request):
    corporations = EveCorporation.objects.all()
    response = []
    for corporation in corporations:
        payload = {
            "corporation_id": corporation.corporation_id,
            "corporation_name": corporation.name,
            "corporation_type": corporation.corporation_type,
        }
        if EveAlliance.objects.filter(
            alliance_id=corporation.alliance_id
        ).exists():
            alliance = EveAlliance.objects.get(
                alliance_id=corporation.alliance_id
            )
            payload["alliance_id"] = alliance.alliance_id
            payload["alliance_name"] = alliance.name
        response.append(payload)
    return response


@router.get(
    "/corporations/{corporation_id}",
    response=CorporationResponse,
    auth=AuthBearer(),
    summary="Get a corporation by ID",
)
def get_corporation_by_id(request, corporation_id: int):
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    response = {
        "corporation_id": corporation.corporation_id,
        "corporation_name": corporation.corporation_name,
        "corporation_type": corporation.corporation_type,
    }
    if EveAlliance.objects.filter(
        alliance_id=corporation.alliance_id
    ).exists():
        alliance = EveAlliance.objects.get(alliance_id=corporation.alliance_id)
        response["alliance_id"] = alliance.alliance_id
        response["alliance_name"] = alliance.name
    return response
