"""Shared tribe endpoint serialization helpers."""

from tribes.endpoints.groups.schemas import CharacterRefSchema


def user_to_character_ref(user) -> CharacterRefSchema | None:
    try:
        char = user.eveplayer.primary_character
        if char:
            return CharacterRefSchema(
                character_id=char.character_id,
                character_name=char.character_name,
            )
    except Exception:
        pass
    return None
