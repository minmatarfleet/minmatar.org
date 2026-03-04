from typing import List, Optional
from pydantic import BaseModel


class CharacterRefSchema(BaseModel):
    character_id: int
    character_name: str = ""


class QualifyingAssetTypeSchema(BaseModel):
    type_id: int
    type_name: str = ""
    minimum_count: int = 1
    location_id: Optional[int] = None


class QualifyingSkillSchema(BaseModel):
    skill_type_id: int
    skill_name: str = ""
    minimum_level: int = 5


class RequirementSchema(BaseModel):
    id: int
    asset_types: List[QualifyingAssetTypeSchema] = []
    qualifying_skills: List[QualifyingSkillSchema] = []


class TribeGroupSchema(BaseModel):
    id: int
    tribe_id: int
    tribe_name: str
    name: str
    description: str
    discord_channel_id: Optional[int] = None
    chief: Optional[CharacterRefSchema] = None
    ship_type_ids: List[int] = []
    blueprint_type_ids: List[int] = []
    is_active: bool
    member_count: int = 0
    requirements: List[RequirementSchema] = []
