from pydantic import BaseModel
from typing import List, Optional


class EvePrimaryCharacterSchema(BaseModel):
    character_id: int
    character_name: str
    corporation_id: Optional[int]
    corporation_name: Optional[str]
    alliance_id: Optional[int]
    alliance_name: Optional[str]
    scopes: List[str]


class DiscordUserSchema(BaseModel):
    id: int
    discord_tag: str
    avatar: Optional[str]


class UserProfileSchema(BaseModel):
    # django stuff
    user_id: int
    username: str
    permissions: List[str]
    is_staff: bool
    is_superuser: bool

    # eve stuff
    eve_character_profile: Optional[EvePrimaryCharacterSchema]

    # discord stuff
    discord_user_profile: Optional[DiscordUserSchema]
