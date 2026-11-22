"""Request and response schemas for /api/voice."""

from datetime import datetime
from typing import Optional

from ninja import Schema


class VoiceCharacter(Schema):
    character_id: int
    character_name: str


class VoiceFleetAccess(Schema):
    fleet_id: int
    branch: int
    branch_name: str
    placement: str
    commander: bool


class VoiceStatusResponse(Schema):
    character_id: int
    character_name: str
    display_name: str
    admitted: bool
    banned: bool
    reason: str
    community: bool
    fleets: list[VoiceFleetAccess]
    certificate_count: int
    # "guest" (EVE sign-in on /voice) or "member" (site account)
    signed_in_as: str
    # A member's characters, to pick which one connects
    characters: list[VoiceCharacter]


class VoiceConnectRequest(Schema):
    character_id: Optional[int] = None


class VoiceConnectResponse(Schema):
    url: str
    expires_in_seconds: int


class VoiceCertificateResponse(Schema):
    id: int
    fingerprint: str
    created_at: datetime
    last_used_at: Optional[datetime]


class VoiceCoFc(Schema):
    character_id: int
    character_name: str


class VoiceFleetResponse(Schema):
    fleet_id: int
    uses_mumble: bool
    can_manage_voice: bool
    can_ban: bool
    branch: Optional[int]
    branch_name: Optional[str]
    wing_channels: dict[str, str]
    channel_choices: list[str]
    co_fcs: list[VoiceCoFc]


class VoiceCharacterRequest(Schema):
    character_id: int


class VoiceWingsRequest(Schema):
    # in-game wing id -> channel name; an empty map clears it
    wing_channels: dict[str, str]


class VoiceKickRequest(Schema):
    character_id: int
    message: str = ""


class VoiceBanRequest(Schema):
    character_id: int
    reason: str = ""
    # Empty: until lifted
    expires_at: Optional[datetime] = None


class VoiceBanResponse(Schema):
    id: int
    character_id: int
    character_name: str
    reason: str
    expires_at: Optional[datetime]


class VoiceInternalLookupRequest(Schema):
    identity_id: Optional[int] = None
    character_id: Optional[int] = None
    cert_hash: str = ""


class VoiceInternalRedeemRequest(Schema):
    password: str
    cert_hash: str = ""
