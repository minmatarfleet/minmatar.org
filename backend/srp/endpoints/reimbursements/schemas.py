from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel


class SrpCategory(str, Enum):
    LOGISTICS = "logistics"
    SUPPORT = "support"
    DPS = "dps"
    CAPITAL = "capital"


class CreateEveFleetReimbursementRequest(BaseModel):
    external_killmail_link: str
    fleet_id: int = None
    is_corp_ship: bool = False
    category: Optional[SrpCategory] = None
    comments: Optional[str] = None
    combat_log_id: Optional[int] = None


class UpdateEveFleetReimbursementRequest(BaseModel):
    status: Literal["pending", "approved", "rejected", "withdrawn"]


class SrpPatchResult(BaseModel):
    database_update_status: str
    evemail_status: str


class EveFleetReimbursementResponse(BaseModel):
    """Represents a SRP request."""

    id: int
    fleet_id: Optional[int] = None
    external_killmail_link: str
    status: str
    character_id: int
    character_name: str
    primary_character_id: int
    primary_character_name: str
    ship_type_id: int
    ship_name: str
    killmail_id: int
    amount: int
    is_corp_ship: bool
    corp_id: Optional[int] = None
    category: Optional[SrpCategory] = None
    comments: Optional[str] = None
    combat_log_id: Optional[int] = None
