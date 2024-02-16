from typing import List, Optional

from pydantic import BaseModel


class EveCharacterSchema(BaseModel):
    """Represents a primary character in eve."""

    character_id: int
    character_name: str
    corporation_id: int
    corporation_name: str
    scopes: List[str]


class DiscordUserSchema(BaseModel):
    """Represents a discord user."""

    id: int
    discord_tag: str
    avatar: Optional[str]


class UserProfileSchema(BaseModel):
    """Represents a user profile with attached eve and discord profiles."""

    # django stuff
    user_id: int
    username: str
    permissions: List[str]
    is_staff: bool
    is_superuser: bool

    # eve stuff
    eve_character_profile: Optional[EveCharacterSchema]

    # discord stuff
    discord_user_profile: Optional[DiscordUserSchema]
