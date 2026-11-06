from typing import Optional

from pydantic import BaseModel


class ChiefCandidateSchema(BaseModel):
    user_id: int
    # The pilot's main.
    character_id: int
    character_name: str
    # The character the search matched, when it isn't the main.
    matched_character_name: str = ""


class SetChiefRequest(BaseModel):
    # None empties the seat.
    user_id: Optional[int] = None


class ChiefSeatSchema(BaseModel):
    tribe_id: int
    tribe_group_id: Optional[int] = None
    user_id: Optional[int] = None
    character_id: Optional[int] = None
    character_name: str = ""
