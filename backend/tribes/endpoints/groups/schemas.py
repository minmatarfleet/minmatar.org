from typing import Any, List, Optional
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


class AffiliationRefSchema(BaseModel):
    id: int
    name: str


class TribeGroupSchema(BaseModel):
    id: int
    tribe_id: int
    tribe_name: str
    code: str = ""
    name: str
    description: str
    content: str = ""
    discord_channel_id: Optional[int] = None
    chief: Optional[CharacterRefSchema] = None
    is_active: bool
    member_count: int = 0
    requirements: List[RequirementSchema] = []
    ranks: List[TribeGroupRankSchema] = []
    required_token_type: Optional[str] = None
    require_off_trial: bool = False
    allowed_affiliations: List[AffiliationRefSchema] = []
    can_apply: bool = False
    can_manage: bool = False


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


class TribeGroupRosterEntrySchema(BaseModel):
    """Public roster row — primary character only (no alts)."""

    user_id: int
    primary_character_id: Optional[int] = None
    primary_character_name: str = ""
    corporation_id: Optional[int] = None
    corporation_name: Optional[str] = None
    rank_id: Optional[int] = None
    rank_code: Optional[str] = None
    rank_name: Optional[str] = None
    rank_sort_order: Optional[int] = None
    approved_at: Optional[str] = None


class TribeGroupGrowthSchema(BaseModel):
    months: List[dict]
    counts: List[int]


class TribeGroupShowcaseContributorSchema(BaseModel):
    character_id: Optional[int] = None
    character_name: str = ""
    metric_key: str = ""
    metric_value: Any = 0


class TribeGroupShowcaseSchema(BaseModel):
    group_id: int
    group_code: str = ""
    group_name: str = ""
    period: str = ""
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    manual: bool = False
    message: str = ""
    totals: dict = {}
    columns: List[str] = []
    contributors: List[TribeGroupShowcaseContributorSchema] = []
