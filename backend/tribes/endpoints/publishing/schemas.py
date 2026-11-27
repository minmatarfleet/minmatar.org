"""Schemas for tribe group publishing settings and pickers."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from tribes.schemas import HostGroupRef


class PublishingPolicy(str, Enum):
    CHIEFS = "chiefs"
    CHOSEN = "chosen"
    MEMBERS = "members"


class PublishingKind(str, Enum):
    POST = "post"
    FLEET = "fleet"
    EVENT = "event"


class DiscordChannelKind(str, Enum):
    TEXT = "text"
    VOICE = "voice"


class PublisherSchema(BaseModel):
    character_id: int
    character_name: str


class TribeGroupPublishingSchema(BaseModel):
    group_id: int
    post_policy: PublishingPolicy
    fleet_policy: PublishingPolicy
    event_policy: PublishingPolicy
    post_publishers: List[PublisherSchema]
    fleet_publishers: List[PublisherSchema]
    event_publishers: List[PublisherSchema]
    allow_alliance_posts: bool
    allow_open_fleets: bool
    fleets_enabled: bool = True
    events_enabled: bool = True
    track_mining_by_default: bool = False
    roundup_enabled: bool = False
    roundup_hour: int = 20
    # Discord ids are strings: they don't fit a JavaScript number.
    discord_channel_id: Optional[str] = None
    effective_discord_channel_id: Optional[str] = None
    effective_discord_channel_name: Optional[str] = None
    discord_role_name: Optional[str] = None


class TribeGroupPublishingPatch(BaseModel):
    """Every field optional; left out means unchanged."""

    post_policy: Optional[PublishingPolicy] = None
    fleet_policy: Optional[PublishingPolicy] = None
    event_policy: Optional[PublishingPolicy] = None
    post_publisher_character_ids: Optional[List[int]] = None
    fleet_publisher_character_ids: Optional[List[int]] = None
    event_publisher_character_ids: Optional[List[int]] = None
    allow_alliance_posts: Optional[bool] = None
    allow_open_fleets: Optional[bool] = None
    fleets_enabled: Optional[bool] = None
    events_enabled: Optional[bool] = None
    track_mining_by_default: Optional[bool] = None
    roundup_enabled: Optional[bool] = None
    # EVE hour of the daily roundup.
    roundup_hour: Optional[int] = Field(default=None, ge=0, le=23)
    # null clears the group's channel (the tribe's channel is used). A
    # string of digits is accepted (Discord ids don't fit a JS number).
    discord_channel_id: Optional[int] = None


class PublishableGroupSchema(HostGroupRef):
    member_count: int
    allow_alliance_posts: bool
    allow_open_fleets: bool
    # The fleet form ticks Track mining by default for this group.
    track_mining_by_default: bool = False


class DiscordChannelSchema(BaseModel):
    # Discord ids are strings: they don't fit a JavaScript number.
    id: str
    name: str
    type: str


class CorporationFollowDecision(str, Enum):
    APPROVE = "approve"
    REVOKE = "revoke"


class CorporationFollowDecisionRequest(BaseModel):
    decision: CorporationFollowDecision


class GroupCorporationFollowSchema(BaseModel):
    """A corporation that asked for (or gets) the group's fleet posts in
    its own Discord."""

    follow_id: int
    corporation_id: int
    corporation_name: str
    channel_name: str
    # requested, approved or revoked.
    status: str
    requested_at: datetime
    decided_by_name: Optional[str] = None
    decided_at: Optional[datetime] = None
    # False when the last forwarded post failed (None: nothing sent yet).
    last_delivery_ok: Optional[bool] = None
