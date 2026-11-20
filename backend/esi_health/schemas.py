from datetime import date, datetime
from typing import List, Literal, Optional

from ninja import Schema


class DirectorHolderResponse(Schema):
    character_id: int
    character_name: str
    # How many required Director permissions this token lacks.
    missing: int
    is_you: bool = False


class DirectorTokenResponse(Schema):
    # "ok", "update" or "missing".
    state: str
    holders: List[DirectorHolderResponse]
    # The permissions the best token lacks, as scope names.
    missing_scopes: List[str]
    # What the missing permissions are used for, e.g. "corporation projects".
    missing_labels: List[str]


class CorporationHealthResponse(Schema):
    corporation_id: int
    name: str
    ticker: str
    members: int
    # Characters whose owner has to log in again.
    needs_readd: int
    # Their owners, split by On Leave.
    pilots_active: int
    pilots_on_leave: int
    # The owners not On Leave: who a message to this corporation reaches.
    active_user_ids: List[int]
    # Characters in the corporation with no account on the site.
    unlinked: int
    director_state: str
    director_complete: int
    director_holders: int
    last_messaged: Optional[datetime] = None


class PilotHealthResponse(Schema):
    user_id: int
    username: str
    main_character_id: Optional[int] = None
    main_character_name: str
    corporation_ticker: str
    # Every character to re-add, the main first.
    characters: List[str]
    main_needs_readd: bool
    scope_groups: List[str]
    community_status: str
    on_leave: bool
    discord_linked: bool
    task_opened_at: Optional[datetime] = None
    last_messaged: Optional[datetime] = None
    # When the next message may go out, if a recent one blocks it.
    next_message_at: Optional[datetime] = None


class ScopeRolloutResponse(Schema):
    id: int
    scope: str
    scope_group: str
    label: str
    added_on: date
    # "none", "suggest" or "require".
    mode: str
    updated: int
    total: int
    # "characters" or "corporations".
    unit: str


class ScopeRolloutPatch(Schema):
    mode: Literal["none", "suggest", "require"]


class MessageRequest(Schema):
    # The pilots to message. Empty sends to everyone who needs to re-add
    # and isn't On Leave or messaged in the last week.
    user_ids: List[int] = []


class MessageResponse(Schema):
    sent: int
    on_leave: int
    recently_messaged: int
    nothing_to_fix: int
    no_discord: int
