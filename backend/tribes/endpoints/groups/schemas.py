from typing import List, Optional
from pydantic import BaseModel


class TribeGroupActivityRecordSchema(BaseModel):
    """Single activity record for timeline display."""

    id: int
    created_at: str
    activity_type: str
    activity_type_display: str
    character_id: Optional[int] = None
    character_name: str = ""
    user_id: Optional[int] = None
    username: str = ""
    source_type_id: Optional[int] = None
    target_type_id: Optional[int] = None
    quantity: Optional[float] = None
    unit: str = ""
    reference_type: str
    reference_id: str


class TribeGroupActivityListSchema(BaseModel):
    """Paginated list of tribe group activity records."""

    items: List[TribeGroupActivityRecordSchema]
    total: int
    limit: int
    offset: int


class TribeActivityRecordSchema(TribeGroupActivityRecordSchema):
    """Activity record with optional group context (for tribe-level activity list)."""

    group_id: Optional[int] = None
    group_name: str = ""


class TribeActivityListSchema(BaseModel):
    """Paginated list of tribe activity records (all groups)."""

    items: List[TribeActivityRecordSchema]
    total: int
    limit: int
    offset: int


class CharacterRefSchema(BaseModel):
    character_id: int
    character_name: str = ""


class QualifyingAssetTypeSchema(BaseModel):
    type_id: int
    type_name: str = ""
    location_ids: List[int] = []


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
    is_active: bool
    member_count: int = 0
    requirements: List[RequirementSchema] = []
