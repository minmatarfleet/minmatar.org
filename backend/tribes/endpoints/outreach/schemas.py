from typing import Optional
from pydantic import BaseModel


class CandidateSchema(BaseModel):
    character_id: int
    character_name: str
    user_id: int
    skillset_id: int
    skillset_name: str
    progress: float
    missing_skills: int = 0
    already_outreached: bool = False


class OutreachSchema(BaseModel):
    id: int
    tribe_group_id: int
    character_id: int
    character_name: str
    sent_by_id: Optional[int] = None
    sent_at: str
    notes: str


class RecordOutreachRequest(BaseModel):
    character_id: int
    notes: str = ""
