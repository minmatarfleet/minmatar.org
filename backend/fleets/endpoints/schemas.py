"""Request/response models and enums for fleet API endpoints."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class EveFleetType(str, Enum):
    STRATEGIC = "strategic"
    NON_STRATEGIC = "non_strategic"
    TRAINING = "training"
    NPSI = "npsi"


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
    audience: Optional[str] = None
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
    short_name: str
    staging_active: bool


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
    # FC-assigned cyno system; only serialized for the FC and the pilot.
    solar_system_id: Optional[int] = None
    solar_system_name: Optional[str] = None

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


class AssignRoleVolunteerSystemRequest(BaseModel):
    """FC assigns (or clears) the system for a cyno volunteer."""

    solar_system_id: Optional[int] = None
    solar_system_name: Optional[str] = Field(default=None, max_length=255)


class EveFleetShipVolunteerResponse(BaseModel):
    id: int
    character_id: int
    character_name: str
    fitting_id: Optional[int] = None
    fleet_fitting_id: Optional[int] = None
    fitting_name: str
    ship_id: int


class EveFleetFittingRefitOption(BaseModel):
    id: int
    name: str


class EveFleetCompositionEntryResponse(BaseModel):
    """One ship in the fleet's effective composition."""

    key: str
    fitting_id: Optional[int] = None
    fleet_fitting_id: Optional[int] = None
    name: str
    ship_id: int
    ship_name: str
    ship_group: str = ""
    role: str
    source: str
    eft_format: str
    refits: List[EveFleetFittingRefitOption]
    module_slots: Dict[str, str] = {}


class CreateEveFleetFittingRequest(BaseModel):
    """Add a catalog fitting (fitting_id) or a manual EFT fit (eft_format)."""

    fitting_id: Optional[int] = None
    eft_format: Optional[str] = None
    role: str = "primary"


class EveFleetFittingRefitModule(BaseModel):
    name: str
    quantity: int
    type_id: Optional[int] = None


class EveFleetFittingRefitResponse(BaseModel):
    id: int
    fitting_id: Optional[int] = None
    fleet_fitting_id: Optional[int] = None
    fitting_name: str
    ship_id: int
    refit_id: Optional[int] = None
    name: str
    cargo_modules: str
    modules: List[EveFleetFittingRefitModule]
    notes: str
    eft_format: str = ""
    esi_fitting_id: Optional[int] = None


class EveFleetRefitSwap(BaseModel):
    """One slot swap: the fitted module and the cargo module replacing it."""

    module_out: str = Field(max_length=255)
    module_in: str = Field(max_length=255)


class CreateEveFleetFittingRefitRequest(BaseModel):
    fitting_id: Optional[int] = None
    fleet_fitting_id: Optional[int] = None
    refit_id: Optional[int] = None
    name: Optional[str] = Field(default=None, max_length=255)
    cargo_modules: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=200)
    # Custom refit built from slot swaps; cargo_modules/notes derive from
    # it when omitted and the refit EFT is saved in-game under the FC.
    swaps: Optional[List[EveFleetRefitSwap]] = None


class EveFleetFittingAccessResponse(BaseModel):
    """Whether the FC can save refits / custom fits in-game (ESI scope)."""

    can_publish: bool
    scope: str
    token_type: str
    character_id: Optional[int] = None
    character_name: Optional[str] = None


class EveFleetSupplyEntryResponse(BaseModel):
    """Availability of one composition entry at the fleet's staging location."""

    key: str
    fitting_id: Optional[int] = None
    fleet_fitting_id: Optional[int] = None
    contracts: Optional[int] = None
    market_fits: Optional[int] = None
    market_missing: List[str] = []


class EveFleetSupplyResponse(BaseModel):
    entries: List[EveFleetSupplyEntryResponse]


class ShipSelection(BaseModel):
    """Which composition entry a character brings (both ids null = not flying)."""

    character_id: int
    fitting_id: Optional[int] = None
    fleet_fitting_id: Optional[int] = None


class MyFleetPilotResponse(BaseModel):
    character_id: int
    character_name: str
    recent_fleets: bool
    selection: Optional[ShipSelection] = None


class SetMyShipVolunteersRequest(BaseModel):
    selections: List[ShipSelection]


class MyFleetFittingResponse(BaseModel):
    """A custom EFT fit the caller has used on a previous fleet."""

    name: str
    ship_id: int
    ship_name: str
    eft_format: str
