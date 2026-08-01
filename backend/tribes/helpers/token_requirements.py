"""ESI token type requirements for tribe group character commits."""

from eveonline.models import EveCharacter
from eveonline.scopes import TokenType, token_satisfies_type
from tribes.models import TribeGroup


def character_has_required_token(
    character: EveCharacter, tribe_group: TribeGroup
) -> bool:
    """
    True when the tribe group has no required token type, or the character's
    live ESI token satisfies that type. Suspended / missing tokens fail.
    """
    required = (tribe_group.required_token_type or "").strip()
    if not required:
        return True
    if not character.token or getattr(character, "esi_suspended", False):
        return False
    try:
        token_type = TokenType(required)
    except ValueError:
        return True
    return token_satisfies_type(character.token, token_type)


def characters_missing_required_token(
    characters: list[EveCharacter], tribe_group: TribeGroup
) -> list[EveCharacter]:
    """Return characters that fail the group's required token type check."""
    return [
        c
        for c in characters
        if not character_has_required_token(c, tribe_group)
    ]


def token_requirement_error_detail(
    characters: list[EveCharacter], required_token_type: str
) -> str:
    """Build a 400 detail naming characters that need a token upgrade."""
    names = ", ".join(c.character_name for c in characters)
    if len(characters) == 1:
        return f"Character {names} requires a {required_token_type} ESI token."
    return f"Characters {names} require a {required_token_type} ESI token."
