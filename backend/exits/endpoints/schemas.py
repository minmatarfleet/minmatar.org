from datetime import datetime
from typing import Optional

from ninja import Schema


class DepartureGroupResponse(Schema):
    """One person who left: a character, with alts that left with them."""

    departure_ids: list[int]
    character_id: int
    character_name: str
    alt_names: list[str]
    registered: bool
    months_in_corporation: Optional[int]
    first_missing_at: datetime
    destination_corporation_id: Optional[int]
    destination_name: Optional[str]
    # exit or alliance_move
    kind: str
    destination_is_npc: bool
    # "" (not answered), kicked_inactive, kicked_other or left
    reason: str
    can_rejoin: Optional[bool]
    note: str
    # The active can't-rejoin flag, if any.
    flag_id: Optional[int]
    survey_sent_at: Optional[datetime]


class DepartureAnswerRequest(Schema):
    departure_ids: list[int]
    reason: str
    can_rejoin: Optional[bool] = None
    note: str = ""


class FlagClearResponse(Schema):
    cleared: bool


class HistoryEntryResponse(Schema):
    """What a CEO said when this pilot (or an alt) left their corporation."""

    departure_id: int
    corporation_id: int
    corporation_name: str
    left_at: datetime
    # kicked_inactive, kicked_other or left
    reason: str
    can_rejoin: Optional[bool]
    note: str
    answered_by_name: str
    # The entry carries a can't-rejoin flag that hasn't been cleared.
    flag_active: bool
