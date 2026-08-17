from typing import List, Optional
from pydantic import BaseModel


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


class TribeGroupRankSchema(BaseModel):
    id: int
    code: str
    name: str
    sort_order: int = 0


class TribeGroupSchema(BaseModel):
    id: int
    tribe_id: int
    tribe_name: str
    code: str = ""
    name: str
    description: str
    discord_channel_id: Optional[int] = None
    chief: Optional[CharacterRefSchema] = None
    is_active: bool
    member_count: int = 0
    requirements: List[RequirementSchema] = []
    ranks: List[TribeGroupRankSchema] = []
    required_token_type: Optional[str] = None


class TribeGroupReportSchema(BaseModel):
    """Town hall / member report for one tribe group."""

    group_id: int
    group_code: str
    group_name: str = ""
    view: str
    scope: str
    period: str
    period_start: str
    period_end: str
    generated_at: str
    manual: bool = False
    message: str = ""
    columns: List[str] = []
    rows: List[dict] = []
    totals: dict = {}
