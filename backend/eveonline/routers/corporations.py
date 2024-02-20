from typing import List

from ninja import Router, Schema

from authentication import AuthBearer
from eveonline.models import EveCorporation

router = Router(tags=["Corporations"])


class CorporationResponse(Schema):
    corporation_id: int
    corporation_name: str
    alliance_id: int
    alliance_name: str
    corporation_type: str


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
        response.append(
            {
                "corporation_id": corporation.corporation_id,
                "corporation_name": corporation.name,
                "alliance_id": corporation.alliance.alliance_id,
                "alliance_name": corporation.alliance.name,
                "corporation_type": corporation.corporation_type,
            }
        )
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
        "alliance_id": corporation.alliance.alliance_id,
        "alliance_name": corporation.alliance.alliance_name,
        "corporation_type": corporation.corporation_type,
    }
    return response
