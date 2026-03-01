from typing import Optional
from pydantic import BaseModel

from tribes.endpoints.groups.schemas import CharacterRefSchema


class TribeSchema(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    content: str
    image_url: Optional[str] = None
    banner_url: Optional[str] = None
    discord_channel_id: Optional[int] = None
    chief: Optional[CharacterRefSchema] = None
    is_active: bool
    group_count: int = 0
    total_member_count: int = 0
