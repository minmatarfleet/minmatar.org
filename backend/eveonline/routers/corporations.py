import logging
from enum import Enum
from typing import List, Optional

from eveuniverse.models import EveFaction
from ninja import Router, Schema

from authentication import AuthBearer
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EvePrimaryCharacter,
)

logger = logging.getLogger(__name__)

router = Router(tags=["Corporations"])


class CorporationType(str, Enum):
    ALLIANCE = "alliance"
    ASSOCIATE = "associate"
    MILITIA = "militia"
    PUBLIC = "public"


class CorporationMemberResponse(Schema):
    character_id: int
    character_name: str
    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None


class CorporationResponse(Schema):
    corporation_id: int
    corporation_name: str
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None
    faction_id: Optional[int] = None
    faction_name: Optional[str] = None
    type: CorporationType
    members: List[CorporationMemberResponse] = []
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
def get_corporations(
    request, corporation_type: Optional[CorporationType] = None
):
    if corporation_type:
        logger.info("Getting corporations of type %s", corporation_type)
    match corporation_type:
        case CorporationType.ALLIANCE:
            logger.info("Getting alliance corporations")
            corporations = EveCorporation.objects.filter(
                alliance__alliance_id=99011978
            )
        case CorporationType.ASSOCIATE:
            logger.info("Getting associate corporations")
            corporations = EveCorporation.objects.filter(
                alliance__alliance_id=99012009
            )
        case CorporationType.MILITIA:
            logger.info("Getting militia corporations")
            corporations = EveCorporation.objects.filter(faction__id=500002)
        case _:
            logger.info("Getting public corporations")
            corporations = EveCorporation.objects.all()
    response = []
    for corporation in corporations:
        payload = {
            "corporation_id": corporation.corporation_id,
            "corporation_name": corporation.name,
            "type": corporation.type,
            "active": corporation.active,
        }
        if (
            corporation.alliance
            and EveAlliance.objects.filter(
                alliance_id=corporation.alliance.alliance_id
            ).exists()
        ):
            alliance = EveAlliance.objects.get(
                alliance_id=corporation.alliance.alliance_id
            )
            payload["alliance_id"] = alliance.alliance_id
            payload["alliance_name"] = alliance.name

        if (
            corporation.faction
            and EveFaction.objects.filter(id=corporation.faction_id).exists()
        ):
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
        "corporation_name": corporation.name,
        "type": corporation.type,
        "active": corporation.active,
        "members": [],
    }
    # populate alliance details
    if (
        corporation.alliance
        and EveAlliance.objects.filter(
            alliance_id=corporation.alliance.alliance_id
        ).exists()
    ):
        alliance = EveAlliance.objects.get(
            alliance_id=corporation.alliance.alliance_id
        )
        response["alliance_id"] = alliance.alliance_id
        response["alliance_name"] = alliance.name

    # populate faction details
    if (
        corporation.faction
        and EveFaction.objects.filter(id=corporation.faction_id).exists()
    ):
        faction = EveFaction.objects.get(id=corporation.faction_id)
        response["faction_id"] = faction.id
        response["faction_name"] = faction.name

    # populate members
    characters = EveCharacter.objects.filter(corporation_id=corporation_id)
    for character in characters:
        primary_character = EvePrimaryCharacter.objects.filter(
            character=character
        ).first()
        payload = {
            "character_id": character.character_id,
            "character_name": character.character_name,
        }
        if primary_character:
            payload["primary_character_id"] = primary_character.character_id
            payload["primary_character_name"] = (
                primary_character.character.character_name
            )
        response["members"].append(payload)
    return response
