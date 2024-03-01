from enum import Enum
from typing import List, Optional

from eveuniverse.models import EveFaction
from ninja import Router, Schema

from authentication import AuthBearer
from eveonline.models import EveAlliance, EveCorporation

router = Router(tags=["Corporations"])


class CorporationType(str, Enum):
    ALLIANCE = "alliance"
    CORPORATION = "corporation"
    MILITIA = "militia"
    PUBLIC = "public"


class CorporationResponse(Schema):
    corporation_id: int
    corporation_name: str
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None
    faction_id: Optional[int] = None
    faction_name: Optional[str] = None
    type: CorporationType
    active: bool


class CorporationApplicationResponse(Schema):
    status: str
    description: str
    corporation_id: int


class CreateCorporationRequest(Schema):
    corporation_id: int


@router.get(
    "/corporations",
    response=List[CorporationResponse],
    summary="Get all corporations",
)
def get_corporations(request):
    corporations = EveCorporation.objects.all()
    response = []
    for corporation in corporations:
        payload = {
            "corporation_id": corporation.corporation_id,
            "corporation_name": corporation.name,
            "type": corporation.type,
            "active": corporation.active,
        }
        if EveAlliance.objects.filter(
            alliance_id=corporation.alliance_id
        ).exists():
            alliance = EveAlliance.objects.get(
                alliance_id=corporation.alliance_id
            )
            payload["alliance_id"] = alliance.alliance_id
            payload["alliance_name"] = alliance.name

        if EveFaction.objects.filter(id=corporation.faction_id).exists():
            faction = EveFaction.objects.get(id=corporation.faction_id)
            payload["faction_id"] = faction.id
            payload["faction_name"] = faction.name

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
