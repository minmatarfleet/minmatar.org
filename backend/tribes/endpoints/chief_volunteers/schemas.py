from typing import Optional

from pydantic import BaseModel


class ChiefVolunteerSchema(BaseModel):
    id: int
    tribe_id: int
    tribe_name: str
    # Empty for the tribe chief seat.
    tribe_group_id: Optional[int] = None
    seat_name: str
    user_id: int
    # The volunteer's main.
    character_id: Optional[int] = None
    character_name: str = ""
    note: str = ""
    # pending, appointed, declined (Not now) or closed (someone else got it).
    status: str
    created_at: str
    decided_at: Optional[str] = None


class VolunteerRequest(BaseModel):
    # Empty volunteers for the tribe chief seat.
    tribe_group_id: Optional[int] = None
    note: str = ""


class DiscordChiefActionRequest(BaseModel):
    discord_user_id: int
