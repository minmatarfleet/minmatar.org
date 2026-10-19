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


class TribeAboutPilotSchema(BaseModel):
    character_id: Optional[int] = None
    character_name: str = ""
    value: float = 0


class TribeAboutGroupSchema(BaseModel):
    id: int
    code: str = ""
    name: str
    member_count: int = 0
    manual: bool = False
    totals: dict = {}
    highlights: dict = {}
    top_pilots: list[TribeAboutPilotSchema] = []


class TribeAboutCorporationSchema(BaseModel):
    corporation_id: int
    name: str = ""
    ticker: str = ""
    people: int = 0


class TribeAboutGrowthSchema(BaseModel):
    months: list[dict] = []
    counts: list[int] = []


class TribeAboutSchema(BaseModel):
    """A year of the tribe. ``ready`` is false until the cache is built."""

    tribe_id: int
    slug: str = ""
    ready: bool = False
    generated_at: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    people: int = 0
    multi_group_people: int = 0
    growth: TribeAboutGrowthSchema = TribeAboutGrowthSchema()
    corporations: list[TribeAboutCorporationSchema] = []
    corporation_count: int = 0
    character_count: int = 0
    # Lifetime, valued from our stored ESI killmails.
    isk_destroyed: int = 0
    groups: list[TribeAboutGroupSchema] = []
    # Tribe-specific blocks; see tribes.helpers.about.
    capitals: Optional[dict] = None
    supply: Optional[dict] = None
