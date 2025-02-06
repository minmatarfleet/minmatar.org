import logging
from enum import Enum
from typing import List, Optional

from django.contrib.auth.models import User
from eveuniverse.models import EveFaction
from ninja import Router, Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EvePrimaryCharacter,
)
from groups.helpers import PEOPLE_TEAM, TECH_TEAM, user_in_team

logger = logging.getLogger(__name__)

router = Router(tags=["Corporations"])

FL33T_ID = 99011978
BUILD_ID = 99012009


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
    registered: bool = False
    exempt: bool = False


class CorporationResponse(Schema):
    """
    Response for a corporation
    """

    corporation_id: int
    corporation_name: str
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None
    faction_id: Optional[int] = None
    faction_name: Optional[str] = None
    type: CorporationType
    introduction: Optional[str] = None
    biography: Optional[str] = None
    timezones: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    members: List[CorporationMemberResponse] = []
    active: bool


class CorporationInfoResponse(Schema):
    """
    Response for a corporation's info
    """

    corporation_id: int
    corporation_name: str
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None
    faction_id: Optional[int] = None
    faction_name: Optional[str] = None
    type: CorporationType
    introduction: Optional[str] = None
    biography: Optional[str] = None
    timezones: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    active: bool


class CorporationApplicationResponse(Schema):
    status: str
    description: str
    corporation_id: int


class CreateCorporationRequest(Schema):
    corporation_id: int


class CorporationMemberDetails(Schema):
    """Similar to CorporationMemberResponse but for member management"""

    character_id: int
    character_name: str
    user_name: Optional[str] = None
    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None
    registered: bool = False
    exempt: bool = False
    esi_suspended: bool = False
    token_count: int = 0


@router.get(
    "/corporations",
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
            logger.debug("Getting alliance corporations")
            corporations = EveCorporation.objects.filter(
                alliance__alliance_id=99011978
            )
        case CorporationType.ASSOCIATE:
            logger.debug("Getting associate corporations")
            corporations = EveCorporation.objects.filter(
                alliance__alliance_id=99012009
            )
        case CorporationType.MILITIA:
            logger.debug("Getting militia corporations")
            corporations = EveCorporation.objects.filter(faction__id=500002)
        case _:
            logger.debug("Getting public corporations")
            corporations = EveCorporation.objects.all()
    response = []
    for corporation in corporations:
        logger.debug("Processing corporation %s", corporation.name)
        payload = {
            "corporation_id": corporation.corporation_id,
            "corporation_name": corporation.name,
            "type": corporation.type,
            "active": corporation.active,
        }
        if corporation.alliance:
            logger.debug(
                "Populating alliance details for %s", corporation.name
            )
            payload["alliance_id"] = corporation.alliance.alliance_id
            payload["alliance_name"] = corporation.alliance.name

        if corporation.faction:
            logger.debug("Populating faction details for %s", corporation.name)
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
    logger.debug("Finished processing corporations")
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
        "introduction": corporation.introduction,
        "biography": corporation.biography,
        "timezones": (
            corporation.timezones.strip().split(",")
            if corporation.timezones
            else []
        ),
        "requirements": (
            corporation.requirements.strip().split("\n")
            if corporation.requirements
            else []
        ),
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

    characters = EveCharacter.objects.filter(
        corporation__corporation_id=corporation_id
    )
    for character in characters:
        payload = {
            "character_id": character.character_id,
            "character_name": character.character_name,
        }
        if character.exempt:
            payload["exempt"] = True
        if character.token:
            payload["registered"] = True
            primary_character = EvePrimaryCharacter.objects.filter(
                character__token__user=character.token.user
            ).first()
            if (
                primary_character
                and primary_character.character
                and primary_character.character.character_id
                != character.character_id
            ):
                payload["primary_character_id"] = (
                    primary_character.character.character_id
                )
                payload["primary_character_name"] = (
                    primary_character.character.character_name
                )
        response["members"].append(payload)
    return response


@router.get(
    "/corporations/{corporation_id}/info",
    response={200: CorporationInfoResponse, 404: ErrorResponse},
    summary="Get a corporation's info",
)
def get_corporation_info(request, corporation_id: int):
    if not EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).exists():
        return 404, {"detail": "Corporation not found"}
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    response = {
        "corporation_id": corporation.corporation_id,
        "corporation_name": corporation.name,
        "introduction": corporation.introduction,
        "biography": corporation.biography,
        "timezones": (
            corporation.timezones.strip().split(",")
            if corporation.timezones
            else []
        ),
        "requirements": (
            corporation.requirements.strip().split("\n")
            if corporation.requirements
            else []
        ),
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
    return response


@router.get(
    "/corporations/{corporation_id}/members",
    response={200: List[CorporationMemberDetails], 403: ErrorResponse},
    auth=AuthBearer(),
    summary="Get corporation member details (leadership only)",
)
def get_corp_member_details(request, corporation_id: int):
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)

    if not can_manage_corp_members(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")

    response = []

    for character in corp_members(corporation_id):
        char = CorporationMemberDetails(
            character_id=character.character_id,
            character_name=character.character_name,
            esi_suspended=character.esi_suspended,
            exempt=character.exempt,
            token_count=character.tokens.count(),
        )
        if character.token:
            char.user_name = character.token.user.username

        response.append(char)

    return response


@router.get(
    "/managed",
    response=List[int],
    auth=AuthBearer(),
    summary="Get IDs of corporations the current user can manage",
)
def get_managed_corp_ids(request) -> List[int]:
    response = []

    user = request.user
    team_access = user_in_team(user, PEOPLE_TEAM) or user_in_team(
        user, TECH_TEAM
    )

    corporations = EveCorporation.objects.filter(
        alliance__alliance_id__in=(FL33T_ID, BUILD_ID)
    ).prefetch_related("ceo__token__user")

    for corp in corporations:
        if team_access or corp.ceo.token.user == user:
            response.append(corp.corporation_id)

    return response


def can_manage_corp_members(user: User, corporation: EveCorporation) -> bool:
    if corporation.ceo.token.user == user:
        return True
    if user_in_team(user, PEOPLE_TEAM):
        return True
    if user_in_team(user, TECH_TEAM):
        return True
    return False


def corp_members(corp_id: int):
    return EveCharacter.objects.filter(corporation__corporation_id=corp_id)
