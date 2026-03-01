from typing import Any, Dict, Optional
from pydantic import BaseModel


class ActivitySchema(BaseModel):
    id: int
    tribe_group_id: int
    tribe_group_name: str
    user_id: int
    character_id: Optional[int] = None
    activity_type: str
    quantity: float
    unit: str
    description: str
    created_at: str


class LeaderboardEntrySchema(BaseModel):
    user_id: int
    character_id: Optional[int] = None
    character_name: Optional[str] = None
    total: float
    unit: str


class GroupOutputSummarySchema(BaseModel):
    tribe_group_id: int
    tribe_group_name: str
    tribe_id: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    totals: Dict[str, Any]


class LogActivityRequest(BaseModel):
    user_id: int
    character_id: Optional[int] = None
    activity_type: str
    quantity: float
    unit: str
    description: str = ""
