from typing import List, Optional

from pydantic import BaseModel


class InvitationSchema(BaseModel):
    id: int
    tribe_id: int
    tribe_name: str
    tribe_group_id: int
    tribe_group_name: str
    user_id: int
    # The invited pilot's main.
    character_id: Optional[int] = None
    character_name: str = ""
    invited_by_id: Optional[int] = None
    invited_by_character_id: Optional[int] = None
    invited_by_name: str = ""
    note: str = ""
    # pending, accepted, declined, withdrawn or expired. A pending invite
    # past its expiry reads as expired.
    status: str
    created_at: str
    expires_at: str
    responded_at: Optional[str] = None
    # Characters the pilot brought, for accepted invites.
    joined_character_count: Optional[int] = None
    # The invite DM: pending, sent, read, skipped or failed; None when no
    # Discord delivery was made (e.g. the pilot muted invites).
    dm_status: Optional[str] = None
    # Why the DM was skipped or failed, e.g. "No Discord link".
    dm_error: str = ""


class SendInvitationsRequest(BaseModel):
    user_ids: List[int]
    note: str = ""


class AcceptInvitationRequest(BaseModel):
    character_ids: List[int]


class DiscordDeclineRequest(BaseModel):
    discord_user_id: int


class InvitationCandidateSchema(BaseModel):
    user_id: int
    character_id: int
    character_name: str
    # The character the search matched, when it isn't the pilot's main.
    matched_character_name: str = ""
    # None when the pilot can be invited; otherwise member, applied,
    # invited, declined_recently, on_trial or not_eligible.
    blocker: Optional[str] = None
    # applied: the pending application to approve instead.
    membership_id: Optional[int] = None
    # applied: when they applied. declined_recently: when the wait ends.
    blocker_date: Optional[str] = None
