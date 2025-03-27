import logging

from enum import Enum
from typing import List

from django.contrib.auth.models import User
from pydantic import BaseModel

from eveonline.models import EvePrimaryCharacter, EveCharacter


logger = logging.getLogger(__name__)


class TokenType(Enum):
    ALLIANCE = "Alliance"
    ASSOCIATE = "Associate"
    MILITIA = "Militia"
    PUBLIC = "Public"


MILITIA_SCOPES = [
    "esi-characters.read_loyalty.v1",
    "esi-killmails.read_killmails.v1",
    "esi-characters.read_fw_stats.v1",
]

ALLIANCE_SCOPES = [
    "esi-wallet.read_character_wallet.v1",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-characters.read_loyalty.v1",
    "esi-killmails.read_killmails.v1",
    "esi-characters.read_fw_stats.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-assets.read_assets.v1",
] + MILITIA_SCOPES

ASSOCIATE_SCOPES = [
    "esi-planets.manage_planets.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
] + ALLIANCE_SCOPES


def get_token_type_for_scopes_list(scopes: List[str]) -> TokenType:
    if set(scopes).issuperset(set(ALLIANCE_SCOPES)):
        return TokenType.ALLIANCE
    elif set(scopes).issuperset(set(ASSOCIATE_SCOPES)):
        return TokenType.ASSOCIATE
    elif set(scopes).issuperset(set(MILITIA_SCOPES)):
        return TokenType.MILITIA
    else:
        return TokenType.PUBLIC


class CharacterResponse(BaseModel):
    character_id: int
    character_name: str
    type: str = "Public"
    scopes: List[str]
    is_primary: bool = False


class CorporationCharacterResponse(BaseModel):
    character_id: int
    character_name: str
    is_registered: bool = False
    is_primary: bool = False


def user_primary_character(user: User) -> EveCharacter | None:
    """Returns the primary character for a particular User"""

    # New method using the "user" field
    pc = EvePrimaryCharacter.objects.filter(user=user).first()
    if pc:
        return pc.character

    # Fall back to old method using link through ESI token
    q = EvePrimaryCharacter.objects.filter(character__token__user=user)

    if q.count() > 1:
        logger.error(
            "User %s has %d primary characters", user.username, q.count()
        )

    if q.count() >= 1:
        return q.first().character
    else:
        return None


def user_characters(user: User) -> List[EveCharacter]:
    """Returns all the EveCharacters for a particular User"""
    return EveCharacter.objects.filter(token__user=user).all()
