from typing import Optional

from pydantic import BaseModel


class ChiefVolunteerSchema(BaseModel):
    id: int
    tribe_id: int
    tribe_name: str
    # Empty for the tribe chief seat.
    tribe_group_id: Optional[int] = None
    # A group seat's timezone region (US, EU, AU); empty for the tribe seat.
    region: str = ""
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
    # A group's timezone seat (US, EU, AU). Empty picks the pilot's own
    # timezone when that seat is open, else the first open one.
    region: Optional[str] = None
    note: str = ""


class DiscordChiefActionRequest(BaseModel):
    discord_user_id: int
