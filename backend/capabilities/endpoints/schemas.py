"""Response and request bodies of the Training API."""

from ninja import Schema


class ShipResponse(Schema):
    fitting_id: int
    name: str
    ship_type_id: int
    capability: str
    doctrines: list[str]


class ShipStatusResponse(ShipResponse):
    ready: bool
    done: bool
    unlocked: bool
    days: float
    skills: int


class GoalResponse(ShipStatusResponse):
    target: str


class CharacterSummaryResponse(Schema):
    character_id: int
    name: str
    skill_points: int
    account: int | None
    not_for_fleets: bool
    goals: list[GoalResponse]
    goals_ready: int
    all_done: bool
    training: GoalResponse | None
    queued: list[str]
    ready: list[ShipResponse]
    suggestions: list[ShipStatusResponse]
    nothing_close: bool


class AccountResponse(Schema):
    number: int
    characters: list[CharacterSummaryResponse]


class BringShipResponse(ShipResponse):
    accounts: int


class BringRowResponse(Schema):
    capability: str
    ships: list[BringShipResponse]


class TrainingOverviewResponse(Schema):
    accounts: list[AccountResponse]
    unplaced: list[CharacterSummaryResponse]
    bring: list[BringRowResponse]


class RoleResponse(Schema):
    capability: str
    ready: list[ShipResponse]
    fleets_365d: int


class TrainingCharacterResponse(CharacterSummaryResponse):
    account_mates: list[str]
    also_close: list[ShipStatusResponse]
    roles: list[RoleResponse]


class PlanStepResponse(Schema):
    skill_id: int
    name: str
    level: int
    days: float


class PlanCharacterResponse(Schema):
    character_id: int
    name: str
    account: int | None
    ready: bool
    days: float
    is_goal: bool


class TrainingPlanResponse(Schema):
    ship: ShipResponse
    character_id: int
    name: str
    is_goal: bool
    is_training: bool
    target: str
    ready: bool
    ready_steps: list[PlanStepResponse]
    ready_days: float
    optimal_steps: list[PlanStepResponse]
    optimal_days: float
    eve_text: str
    queue_skills: int
    up_next: list[str]
    flown_by: list[str]
    who: list[PlanCharacterResponse]


class ShipOptionResponse(ShipStatusResponse):
    strategic: bool
    added: bool


class AccountOptionResponse(Schema):
    number: int
    characters: list[str]
    size: int
    full: bool
    seen_together: int
    current: bool


class AccountOptionsResponse(Schema):
    character_id: int
    name: str
    current: int | None
    accounts: list[AccountOptionResponse]


class GoalRequest(Schema):
    fitting_id: int


class GoalPatchRequest(Schema):
    first: bool = False
    target: str | None = None


class CharacterPatchRequest(Schema):
    not_for_fleets: bool


class AccountMoveRequest(Schema):
    account: int | None = None
    new_account: bool = False


class TrainingChangeResponse(Schema):
    ok: bool
