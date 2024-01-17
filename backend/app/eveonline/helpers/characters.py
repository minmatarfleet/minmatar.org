from enum import Enum
from pydantic import BaseModel
from typing import List
from django.contrib.auth.models import User
from eveonline.models import EvePrimaryToken, EveCorporation
from esi.models import Token


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


def get_token_type_for_scopes_list(scopes: list[str]) -> TokenType:
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


def get_character_list(user: User) -> List[CharacterResponse]:
    characters = {}
    for token in user.token_set.all():
        if token.character_id not in characters:
            characters[token.character_id] = CharacterResponse(
                character_id=token.character_id,
                character_name=token.character_name,
                scopes=[scope.name for scope in token.scopes.all()],
            )
        else:
            characters[token.character_id].scopes += [
                scope.name for scope in token.scopes.all()
            ]

    # Check if a primary token exists and set the flag
    if EvePrimaryToken.objects.filter(user=user).exists():
        characters[
            EvePrimaryToken.objects.get(user=user).token.character_id
        ].is_primary = True

    # Check scopes for character_id and set type
    for character in characters.values():
        character.type = get_token_type_for_scopes_list(character.scopes)

    return [character for character in characters.values()]


def get_corporation_character_list(
    corporation: EveCorporation,
) -> List[CorporationCharacterResponse]:
    characters = {}
    for character in corporation.evecharacter_set.all():
        characters[character.character_id] = CorporationCharacterResponse(
            character_id=character.character_id,
            character_name=character.character_name,
            is_registered=Token.objects.filter(character_id=character.character_id).exists(),
            is_primary=EvePrimaryToken.objects.filter(
                token__character_id=character.character_id
            ).exists(),
        )

    return [character for character in characters.values()]
