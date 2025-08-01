import logging

from typing import List

from django.contrib.auth.models import User
from pydantic import BaseModel

from audit.models import AuditEntry
from eveonline.models import (
    EvePlayer,
    EvePrimaryCharacter,
    EveCharacter,
    EvePrimaryCharacterChangeLog,
)
from eveonline.scopes import TokenType, scopes_for


logger = logging.getLogger(__name__)


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

    # New method using the EvePlayer entity
    player = user_player(user)
    if player and player.primary_character:
        return player.primary_character

    # Fall-back to old EvePrimaryCharacter
    pc = EvePrimaryCharacter.objects.filter(user=user).first()
    if pc:
        logger.error(
            "Found primary using outdated method 1: %s",
            pc.character.character_name,
        )
        return pc.character

    return None


def user_characters(user: User) -> List[EveCharacter]:
    """Returns all the EveCharacters for a particular User"""
    return EveCharacter.objects.filter(user=user).all()


def character_primary(character: EveCharacter) -> EveCharacter | None:
    """Returns the primary character for a character"""
    if not character:
        return None
    if character.user:
        return user_primary_character(character.user)
    else:
        return user_primary_character(character.token.user)


def set_primary_character(user: User, character: EveCharacter):
    """Sets the primary character for a user"""

    current_primary = user_primary_character(user)
    if current_primary and (current_primary != character):
        EvePrimaryCharacterChangeLog.objects.create(
            username=user.username,
            previous_character_name=current_primary.character_name,
            new_character_name=character.character_name,
        )
        AuditEntry.objects.create(
            user=user,
            character=character,
            old_character_id=current_primary.character_id,
            category="primary_char",
            summary=f"User {user.username} set primary character to {character.character_name}",
        )
        current_primary.is_primary = False
        current_primary.save()
        EvePrimaryCharacter.objects.filter(user=user).delete()

    character.user = user
    character.is_primary = True
    character.save()

    player = user_player(user)
    if player:
        player.primary_character = character
        player.nickname = character.character_name
        player.save()
    else:
        EvePlayer.objects.create(
            user=user,
            primary_character=character,
            nickname=character.character_name,
        )


def user_player(user: User) -> EvePlayer | None:
    return EvePlayer.objects.filter(user=user).first()


def player_characters(player: EvePlayer) -> List[EveCharacter]:
    return user_characters(player.user)


def character_desired_scopes(character: EveCharacter) -> List[str]:
    if not character.esi_token_level:
        return []

    token_type = TokenType(character.esi_token_level)
    if not token_type:
        return []

    return scopes_for(token_type)
