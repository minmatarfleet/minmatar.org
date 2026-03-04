from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class MembershipCharacterSchema(BaseModel):
    id: int
    character_id: int
    character_name: str
    committed_at: Optional[str] = None
    left_at: Optional[str] = None
    # Requirement qualification (for chief viewing members).
    qualifies: Optional[bool] = None
    missing_skills: Optional[bool] = None
    missing_assets: Optional[bool] = None


class MembershipSchema(BaseModel):
    id: int
    user_id: int
    tribe_group_id: int
    tribe_group_name: str
    tribe_id: int
    status: str
    inactive_reason: Optional[str] = None
    requirement_snapshot: Optional[Dict[str, Any]] = None
    created_at: str
    approved_by_id: Optional[int] = None
    approved_at: Optional[str] = None
    left_at: Optional[str] = None
    characters: List[MembershipCharacterSchema] = []


class ApplyToGroupRequest(BaseModel):
    character_ids: List[int]


class AddCharacterRequest(BaseModel):
    character_id: int


class RequirementQualificationSchema(BaseModel):
    """Per-requirement qualification result for one character."""

    requirement_id: str
    display: str
    met: bool
    detail: str


class AvailableCharacterSchema(BaseModel):
    """User character with qualification status for a group's requirements."""

    character_id: int
    character_name: str
    qualifies: bool
    requirements: List[RequirementQualificationSchema] = []
    # When qualifies is False: what they're missing (for simple UI message).
    missing_skills: bool = False
    missing_assets: bool = False


class RefreshAvailableCharacterRequest(BaseModel):
    """Request body for POST characters-available/refresh."""

    character_id: int
