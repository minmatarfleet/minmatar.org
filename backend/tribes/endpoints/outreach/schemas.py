from pydantic import BaseModel


class CandidateSchema(BaseModel):
    character_id: int
    character_name: str
    user_id: int
    skillset_id: int
    skillset_name: str
    progress: float
    missing_skills: int = 0
