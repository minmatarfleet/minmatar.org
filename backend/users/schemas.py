from datetime import datetime
from typing import Any, List, Optional

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
    nickname: Optional[str]


class UserProfileSchema(BaseModel):
    """Represents a user profile with attached eve and discord profiles."""

    # django stuff
    user_id: int
    username: str
    permissions: List[str]
    is_superuser: bool
    community_status: Optional[str] = None

    # eve stuff
    eve_character_profile: Optional[EveCharacterSchema]

    # discord stuff
    discord_user_profile: Optional[DiscordUserSchema]


class DesktopSettingsSchema(BaseModel):
    values: dict[str, Any] = {}
    updated_at: datetime | None = None


class DesktopSettingsPatchSchema(BaseModel):
    # A null value removes the key.
    values: dict[str, Any]
