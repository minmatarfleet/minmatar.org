"""Shared response/request schemas for character endpoints."""

import datetime
from typing import List, Optional

from pydantic import BaseModel


class BasicCharacterResponse(BaseModel):
    character_id: int
    character_name: str


class CharacterResponse(BasicCharacterResponse):
    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None


class CharacterSkillsetResponse(BaseModel):
    name: str
    progress: float
    missing_skills: List[str]


class CharacterAssetResponse(BaseModel):
    type_id: int
    type_name: str
    location_id: int
    location_name: str


class UserCharacter(BaseModel):
    character_id: int
    character_name: str
    is_primary: bool
    corp_id: Optional[int] = None
    corp_name: Optional[str] = None
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None
    esi_token: Optional[str] = None
    token_status: Optional[str] = None
    flags: List[str] = []


class UserCharacterResponse(BaseModel):
    user_id: int
    user_name: str
    discord_id: str
    characters: List[UserCharacter]


class CharacterTokenInfo(BaseModel):
    id: str
    created: datetime.datetime
    expires: datetime.datetime
    can_refresh: bool
    owner_hash: str
    scopes: List[str]
    requested_level: str
    requested_count: int
    actual_level: str
    actual_count: int
    token_state: str


class CharacterTagResponse(BaseModel):
    id: int
    title: str
    description: str
    image_name: Optional[str] = None
