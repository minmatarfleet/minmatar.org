from datetime import datetime
from typing import List

from pydantic import BaseModel


class ResolveKillmailRequest(BaseModel):
    external_killmail_link: str


class CandidateFleetCommanderResponse(BaseModel):
    character_id: int
    character_name: str
    corporation_id: int
    corporation_name: str


class CandidateFleetResponse(BaseModel):
    id: int
    type: str
    start_time: datetime
    objective: str
    fleet_commander: CandidateFleetCommanderResponse


class ResolveKillmailResponse(BaseModel):
    killmail_time: datetime
    killmail_id: int
    victim_character_id: int
    victim_character_name: str
    ship_type_id: int
    ship_name: str
    candidate_fleets: List[CandidateFleetResponse]
