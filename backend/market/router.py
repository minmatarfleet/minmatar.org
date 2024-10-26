import logging
from typing import List

from ninja import Router
from pydantic import BaseModel

from eveonline.models import EveCharacter, EveCorporation
from eveonline.scopes import MARKET_CHARACTER_SCOPES

logger = logging.getLogger(__name__)
router = Router(tags=["Market"])


class MarketCharacterResponse(BaseModel):
    character_id: int
    character_name: str


class MarketCorporationResponse(BaseModel):
    corporation_id: int
    corporation_name: str


@router.get(
    "/characters",
    response=List[MarketCharacterResponse],
    description="List all owned characters with sufficient market scopes",
)
def get_market_characters(request):
    characters = EveCharacter.objects.filter(
        token__scopes__name__in=set(MARKET_CHARACTER_SCOPES),
        token__user=request.user,
    ).distinct()
    response = []
    for character in characters:
        response.append(
            MarketCharacterResponse(
                character_id=character.character_id,
                character_name=character.character_name,
            )
        )

    return response


@router.get(
    "/corporations",
    response=List[MarketCorporationResponse],
    description="List all owned corporations with sufficient market scopes",
)
def get_market_corporations(request):
    corporations = EveCorporation.objects.filter(
        ceo__token__scopes__name__in=set(MARKET_CHARACTER_SCOPES),
        ceo__token__user=request.user,
        alliance__name__in=[
            "Minmatar Fleet Alliance",
            "Minmatar Fleet Associates",
        ],
    ).distinct()
    response = []
    for corporation in corporations:
        response.append(
            MarketCorporationResponse(
                corporation_id=corporation.corporation_id,
                corporation_name=corporation.name,
            )
        )

    return response
