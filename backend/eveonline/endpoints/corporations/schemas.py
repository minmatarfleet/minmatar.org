"""Shared response/request schemas for corporation endpoints."""

from enum import Enum
from typing import List, Optional

from ninja import Schema


class CorporationType(str, Enum):
    ALLIANCE = "alliance"
    ASSOCIATE = "associate"
    MILITIA = "militia"
    PUBLIC = "public"


class CorporationMemberResponse(Schema):
    character_id: int
    character_name: str
    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None
    registered: bool = False
    exempt: bool = False


class CorporationRoleCharacterResponse(Schema):
    character_id: int
    character_name: str


class CorporationResponse(Schema):
    corporation_id: int
    corporation_name: str
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None
    faction_id: Optional[int] = None
    faction_name: Optional[str] = None
    type: CorporationType
    introduction: Optional[str] = None
    biography: Optional[str] = None
    timezones: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    members: List[CorporationMemberResponse] = []
    directors: List[CorporationRoleCharacterResponse] = []
    recruiters: List[CorporationRoleCharacterResponse] = []
    stewards: List[CorporationRoleCharacterResponse] = []
    active: bool


class CorporationInfoResponse(Schema):
    corporation_id: int
    corporation_name: str
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None
    faction_id: Optional[int] = None
    faction_name: Optional[str] = None
    type: CorporationType
    introduction: Optional[str] = None
    biography: Optional[str] = None
    timezones: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    active: bool


class CorporationMemberDetails(Schema):
    character_id: int
    character_name: str
    user_name: Optional[str] = None
    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None
    registered: bool = False
    exempt: bool = False
    esi_suspended: bool = False
    token_count: int = 0
    token_level: str = None
