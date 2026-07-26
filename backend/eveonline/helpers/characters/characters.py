import logging
from typing import List

from django.contrib.auth.models import User
from django.utils import timezone
from pydantic import BaseModel

from audit.models import AuditEntry
from esi.models import Token
from eveonline.models import EvePlayer, EveCharacter
from eveonline.scopes import (
    TokenType,
    scopes_for_groups,
    token_type_str,
)
from tribes.models import (
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
)

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
    player = user_player(user)
    if player and player.primary_character:
        return player.primary_character
    return None


def user_characters(user: User) -> List[EveCharacter]:
    """Returns all the EveCharacters for a particular User"""
    return EveCharacter.objects.filter(user=user).all()


def related_characters(character: EveCharacter) -> List[EveCharacter]:
    """Returns all EveCharacters belonging to the same user as the given character."""
    if not character or not character.user_id:
        return []
    return list(
        EveCharacter.objects.filter(user_id=character.user_id).order_by(
            "character_name"
        )
    )


def character_primary(character: EveCharacter) -> EveCharacter | None:
    """Returns the primary character for a character"""
    if not character:
        return None
    if character.user:
        return user_primary_character(character.user)
    return user_primary_character(character.token.user)


def set_primary_character(user: User, character: EveCharacter):
    """Sets the primary character for a user"""
    current_primary = user_primary_character(user)
    if current_primary and (current_primary != character):
        AuditEntry.objects.create(
            user=user,
            character=character,
            old_character_id=current_primary.character_id,
            category="primary_char",
            summary=f"User {user.username} set primary character to {character.character_name}",
        )
        old_player = user_player(user)
        if old_player and old_player.primary_character == current_primary:
            old_player.primary_character = None
            old_player.save()

    character.user = user
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


def orphan_character(
    character: EveCharacter, *, acting_user: User | None = None
) -> None:
    """Detach a character from its user and ESI tokens; keep synced EVE data."""
    for mc in TribeGroupMembershipCharacter.objects.filter(
        character=character
    ).select_related("membership"):
        TribeGroupMembershipCharacterHistory.objects.create(
            membership=mc.membership,
            character=character,
            action=TribeGroupMembershipCharacterHistory.ACTION_REMOVED,
            at=timezone.now(),
            by=acting_user,
            leave_reason=TribeGroupMembershipCharacterHistory.LEAVE_REASON_VOLUNTARY,
        )
        mc.delete()

    character.user = None
    character.token = None
    character.save(update_fields=["user", "token"])
    Token.objects.filter(character_id=character.character_id).delete()


def player_characters(player: EvePlayer) -> List[EveCharacter]:
    return user_characters(player.user)


def _normalize_token_level(level: str) -> str:
    """Map legacy token level names to current TokenType values."""
    legacy = {"CEO": "Director", "Freight": "Market", "Advanced": "Industry"}
    return legacy.get(level, level)


def merge_scope_groups(
    existing: List[str] | None, *groups: str | None
) -> List[str]:
    """Return scope groups with duplicates removed, preserving order."""
    result = list(existing or [])
    for group in groups:
        normalized = _normalize_token_level((group or "").strip())
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def character_configured_scope_groups(character: EveCharacter) -> List[str]:
    """Scope groups explicitly configured for a character."""
    groups = merge_scope_groups(getattr(character, "esi_scope_groups", None))
    if not groups and character.esi_token_level:
        return merge_scope_groups([], character.esi_token_level)
    if character.esi_token_level:
        groups = merge_scope_groups(
            groups, _normalize_token_level(character.esi_token_level)
        )
    return groups


def character_desired_scopes(character: EveCharacter) -> List[str]:
    """Union of scopes for all of the character's scope groups."""
    groups = character_configured_scope_groups(character)
    if not groups:
        return []
    return scopes_for_groups(groups)


def scope_groups_for_token_add(
    character: EveCharacter | None,
    token_type: TokenType,
) -> List[str]:
    """Scope groups to request in SSO when adding token_type to a character."""
    existing: List[str] = []
    if character is not None:
        existing = character_configured_scope_groups(character)
    return merge_scope_groups(existing, token_type_str(token_type))
