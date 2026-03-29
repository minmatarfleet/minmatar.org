"""Request/response models and enums for fleet API endpoints."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class EveFleetType(str, Enum):
    STRATEGIC = "strategic"
    NON_STRATEGIC = "non_strategic"
    TRAINING = "training"


class EveFleetChannelResponse(BaseModel):
    id: int
    display_name: str
    display_channel_name: Optional[str] = None
    image_url: Optional[str] = None


class EveFleetTrackingResponse(BaseModel):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    is_registered: bool

    class Config:
        from_attributes = True


class EveFleetResponse(BaseModel):
    """Response model for fleet objects."""

    id: int
    type: EveFleetType
    audience: str
    description: str
    objective: Optional[str] = None
    start_time: Optional[datetime] = None
    fleet_commander: int
    doctrine_id: Optional[int] = None
    location: str
    disable_motd: bool = False
    status: Optional[str] = None
    aar_link: Optional[str] = None

    tracking: Optional[EveFleetTrackingResponse] = None


class EveFleetMemberResponse(BaseModel):
    character_id: int
    character_name: str
    ship_type_id: int
    ship_type_name: str
    solar_system_id: int
    solar_system_name: str


class EveFleetLocationResponse(BaseModel):
    location_id: int
    location_name: str
    solar_system_id: int
    solar_system_name: str


class EveFleetUsersResponse(BaseModel):
    fleet_id: int
    user_ids: List[int]


class CreateEveFleetRequest(BaseModel):
    type: EveFleetType
    description: str
    objective: Optional[str] = Field(default=None, max_length=200)
    start_time: datetime
    doctrine_id: Optional[int] = None
    audience_id: int
    location_id: Optional[int] = None
    disable_motd: bool = False
    immediate_ping: bool = False
    status: Optional[str] = None


class UpdateEveFleetRequest(BaseModel):
    type: Optional[EveFleetType] = None
    description: Optional[str] = None
    objective: Optional[str] = Field(default=None, max_length=200)
    start_time: Optional[datetime] = None
    doctrine_id: Optional[int] = None
    audience_id: Optional[int] = None
    location_id: Optional[int] = None
    disable_motd: Optional[bool] = False
    status: Optional[str] = None
    aar_link: Optional[str] = None


class EveFleetMetric(BaseModel):
    fleet_id: int
    members: int
    time_region: str
    location_name: str
    status: str
    fc_corp_name: str
    corporation_id: Optional[int] = None
    corporation_name: Optional[str] = None
    audience_name: str


class EveFleetCommanderMetric(BaseModel):
    user_id: int
    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None
    corporation_id: Optional[int] = None
    corporation_name: Optional[str] = None
    fleet_count: int


class UserActiveFleetResponse(BaseModel):
    character_id: int
    eve_fleet_id: int
    fleet_boss_id: int
    fleet_role: str


class StartFleetRequest(BaseModel):
    """Additional data for starting to track a fleet."""

    fc_character_id: Optional[int] = None


class StartFleetNowRequest(BaseModel):
    """Optional body for quick-start fleet (which character is in the fleet)."""

    fc_character_id: Optional[int] = None
    objective: Optional[str] = Field(default=None, max_length=200)


class EveFleetRoleVolunteerResponse(BaseModel):
    id: int
    character_id: int
    character_name: str
    role: str
    subtype: Optional[str] = None
    quantity: Optional[int] = None

    class Config:
        from_attributes = True


class CreateEveFleetRoleVolunteerRequest(BaseModel):
    character_id: int
    role: str
    subtype: Optional[str] = None
    quantity: Optional[int] = None


class EveFleetFilter(str, Enum):
    ACTIVE = "active"
    UPCOMING = "upcoming"
    RECENT = "recent"
