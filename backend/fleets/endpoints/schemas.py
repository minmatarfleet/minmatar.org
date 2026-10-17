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
    # Campaign fleets. Valid on a response, but deliberately absent from
    # GET /types so the fleet form cannot create one.
    STANDING = "standing"
    GANG = "gang"


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
    is_free_move: bool = False
    has_motd: bool = False

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
    hide_volunteers: bool = False
    status: Optional[str] = None
    aar_link: Optional[str] = None
    campaign_id: Optional[int] = None
    campaign_slug: Optional[str] = None
    roam_report_url: Optional[str] = None

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
    hide_volunteers: bool = False
    immediate_ping: bool = False
    status: Optional[str] = None
    campaign_id: Optional[int] = None


class UpdateEveFleetRequest(BaseModel):
    type: Optional[EveFleetType] = None
    description: Optional[str] = None
    objective: Optional[str] = Field(default=None, max_length=200)
    start_time: Optional[datetime] = None
    doctrine_id: Optional[int] = None
    audience_id: Optional[int] = None
    location_id: Optional[int] = None
    disable_motd: Optional[bool] = False
    hide_volunteers: Optional[bool] = None
    status: Optional[str] = None
    aar_link: Optional[str] = None
    campaign_id: Optional[int] = None


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


class EveFleetFitRolesResponse(BaseModel):
    """Roles a composition fit fills. Burst counts are keyed by kind."""

    links: bool = False
    burst_slots: int = 0
    bursts_online: Dict[str, int] = {}
    bursts_fitted: Dict[str, int] = {}
    cyno: bool = False
    logi: bool = False


class EveFleetShipVolunteerResponse(BaseModel):
    id: int
    character_id: int
    character_name: str
    fitting_id: Optional[int] = None
    fleet_fitting_id: Optional[int] = None
    fitting_name: str
    ship_id: int
    # Command bursts the pilot will run online (kinds, canonical order).
    bursts: List[str] = []
    # FC-assigned cyno system; only serialized for the FC and the pilot.
    solar_system_id: Optional[int] = None
    solar_system_name: Optional[str] = None


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
    fit_roles: EveFleetFitRolesResponse = EveFleetFitRolesResponse()


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
    # Command bursts to run online. Omitted: the fit's online bursts.
    bursts: Optional[List[str]] = None


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


class EveFleetKillmailResponse(BaseModel):
    killmail_id: int
    killmail_time: datetime
    outcome: str
    solar_system_id: int
    solar_system_name: str
    victim_ship_type_id: int | None = None
    victim_ship_name: str
    victim_character_id: int | None = None
    victim_character_name: str
    isk_value: int
    fleet_pilots: int
    is_capsule: bool


class EveFleetKillsResponse(BaseModel):
    fleet_id: int
    tracked: bool
    isk_destroyed: int
    isk_lost: int
    ships_destroyed: int
    pods_destroyed: int
    ships_lost: int
    pods_lost: int
    killmails: List[EveFleetKillmailResponse]


class EveFleetRolePilot(BaseModel):
    """A pilot filling a role, from a ship volunteer or their ship in fleet."""

    character_id: int
    character_name: str
    ship_id: int
    ship_name: str
    fitting_name: str = ""
    source: str  # volunteer | in_fleet
    in_fleet: bool = False
    # Bursts of the row's kind this pilot runs (links rows only).
    count: int = 0
    # Set for a volunteered ship; the FC assigns cyno systems through it.
    ship_volunteer_id: Optional[int] = None
    solar_system_id: Optional[int] = None
    solar_system_name: Optional[str] = None


class EveFleetLinkCoverage(BaseModel):
    kind: str
    label: str
    pilots: List[EveFleetRolePilot]


class EveFleetRoleCoverageResponse(BaseModel):
    """Who fills each fleet role, worked out from ships."""

    logi_fc: List[EveFleetRoleVolunteerResponse]
    links: List[EveFleetLinkCoverage]
    cynos: List[EveFleetRolePilot]
    logi: List[EveFleetRolePilot]


class FleetWindowFleet(BaseModel):
    id: int
    type: str
    type_label: str
    title: str
    description: str = ""
    doctrine_name: Optional[str] = None
    location_name: Optional[str] = None
    location_system_id: Optional[int] = None
    location_system_name: Optional[str] = None
    start_time: Optional[datetime] = None
    status: Optional[str] = None
    live: bool
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    fc_character_id: Optional[int] = None
    fc_name: Optional[str] = None
    fc_system_id: Optional[int] = None
    fc_system_name: Optional[str] = None


class FleetWindowShip(BaseModel):
    """One doctrine fit with live and signed-up counts."""

    key: str
    name: str
    ship_type_id: int
    ship_name: str
    role: str
    role_label: str
    flying: int
    signed_up: int


class FleetWindowRole(BaseModel):
    role: str  # links | cyno | logi
    covered: bool


class FleetWindowNeed(BaseModel):
    kind: str  # ship | role
    count: int
    label: str
    ship_type_id: Optional[int] = None


class FleetWindowPilot(BaseModel):
    character_id: int
    character_name: str
    ship_type_id: int
    ship_name: str
    solar_system_id: int
    solar_system_name: str
    docked: bool
    doctrine: bool
    capsule: bool


class FleetWindowAttention(BaseModel):
    # capsule | off_doctrine | docked | away | not_in_fleet (signed up)
    reason: str
    names: List[str]


class FleetWindowLoss(BaseModel):
    killmail_id: int
    killmail_time: datetime
    ship_type_id: Optional[int] = None
    ship_name: str
    isk_value: int
    solar_system_name: str
    srp_filed: bool


class FleetWindowFeedRow(BaseModel):
    """One killmail in the FC's kill feed."""

    killmail_id: int
    killmail_time: datetime
    outcome: str  # kill | loss
    ship_type_id: Optional[int] = None
    ship_name: str = ""
    victim_name: str = ""
    isk_value: int = 0
    solar_system_name: str = ""
    fleet_pilots: int = 0
    capsule: bool = False


class FleetWindowMe(BaseModel):
    character_ids: List[int]
    characters: List[FleetWindowPilot]
    ship_volunteers: Dict[int, str]  # character id -> composition key
    last_loss: Optional[FleetWindowLoss] = None


class FleetWindowCounts(BaseModel):
    in_fleet: int
    with_fc: int
    kills: int
    losses: int
    isk_destroyed: int
    isk_lost: int


class FleetWindowAfterAction(BaseModel):
    pilots: int
    duration_seconds: int
    losses: int
    srp_filed: int
    aar_link: Optional[str] = None


class FleetWindowResponse(BaseModel):
    """Everything the desktop fleet window shows, for one viewer."""

    mode: str  # fc | member | viewer
    fleet: FleetWindowFleet
    counts: FleetWindowCounts
    ships: List[FleetWindowShip]
    roles: List[FleetWindowRole]
    needs: List[FleetWindowNeed]
    me: FleetWindowMe
    # FC only: everyone else gets empty lists.
    pilots: List[FleetWindowPilot] = []
    attention: List[FleetWindowAttention] = []
    after_action: Optional[FleetWindowAfterAction] = None
    feed: List[FleetWindowFeedRow] = []


class MyFleetLoss(BaseModel):
    killmail_id: int
    killmail_time: datetime
    ship_type_id: Optional[int] = None
    ship_name: str = ""
    isk_value: int = 0
    solar_system_name: str = ""
    srp_status: str  # none | pending | approved | rejected
    srp_amount: int = 0


class MyRecentFleet(BaseModel):
    fleet_id: int
    title: str
    type_label: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    live: bool
    was_fc: bool
    kills: int
    losses: int
    isk_destroyed: int
    isk_lost: int
    aar_link: Optional[str] = None
    my_losses: List[MyFleetLoss] = []


class MyFleetSignup(BaseModel):
    fleet_id: int
    character_id: int
    character_name: str
    fit_name: str = ""
    ship_type_id: Optional[int] = None


class MyFleetsResponse(BaseModel):
    """The desktop window's Recent tab and the user's ship sign-ups."""

    fleets: List[MyRecentFleet] = []
    srp_owed: int = 0
    signups: List[MyFleetSignup] = []


class CurrentFleetWindowResponse(BaseModel):
    window: Optional[FleetWindowResponse] = None


class EveFleetResultResponse(BaseModel):
    """Stored kill totals for one fleet; pods count towards ISK, not ships."""

    fleet_id: int
    isk_destroyed: int
    isk_lost: int
    ships_destroyed: int
    pods_destroyed: int
    ships_lost: int
    pods_lost: int


class EveFleetSrpLossResponse(BaseModel):
    """A ship the caller lost in a fleet, on a hull SRP covers."""

    killmail_id: int
    killmail_time: datetime
    character_id: int
    character_name: str
    ship_type_id: int
    ship_name: str
    amount: int
    filed: bool
