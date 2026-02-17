"""GET /corporations - get all corporations."""

import logging
from typing import List, Optional

from ninja import Router

from eveonline.endpoints.corporations.schemas import (
    CorporationResponse,
    CorporationType,
)
from eveonline.models import EveCorporation

logger = logging.getLogger(__name__)

router = Router(tags=["Corporations"])


@router.get(
    "corporations",
    response=List[CorporationResponse],
    summary="Get all corporations",
)
def get_corporations(
    request, corporation_type: Optional[CorporationType] = None
):
    if corporation_type:
        logger.debug("Getting corporations of type %s", corporation_type)
    match corporation_type:
        case CorporationType.ALLIANCE:
            corporations = EveCorporation.objects.filter(
                alliance__alliance_id=99011978
            )
        case CorporationType.ASSOCIATE:
            corporations = EveCorporation.objects.filter(
                alliance__alliance_id=99012009
            )
        case CorporationType.MILITIA:
            corporations = EveCorporation.objects.filter(faction__id=500002)
        case _:
            corporations = EveCorporation.objects.all()
    response = []
    for corporation in corporations:
        payload = {
            "corporation_id": corporation.corporation_id,
            "corporation_name": corporation.name,
            "type": corporation.type,
            "active": corporation.active,
        }
        if corporation.alliance:
            payload["alliance_id"] = corporation.alliance.alliance_id
            payload["alliance_name"] = corporation.alliance.name
        if corporation.faction:
            payload["faction_id"] = corporation.faction.id
            payload["faction_name"] = corporation.faction.name
        payload["introduction"] = corporation.introduction
        payload["biography"] = corporation.biography
        payload["timezones"] = (
            corporation.timezones.strip().split(",")
            if corporation.timezones
            else []
        )
        payload["requirements"] = (
            corporation.requirements.strip().split("\n")
            if corporation.requirements
            else []
        )
        response.append(payload)
    return response
