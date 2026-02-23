from typing import Optional

from pydantic import BaseModel


class FreightContractResponse(BaseModel):
    """Single freight contract for list/views."""

    contract_id: int
    status: str
    start_location_name: str
    end_location_name: str
    volume: int
    collateral: int
    reward: int
    date_issued: str
    date_completed: Optional[str] = None
    completed_by_character_name: Optional[str] = None


class FreightCharacterStatResponse(BaseModel):
    """Character stats: primary character and completed contract count (e.g. last 30 days)."""

    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None
    completed_contracts_count: int
