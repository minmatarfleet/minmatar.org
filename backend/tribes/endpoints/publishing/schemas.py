"""Schemas for tribe group publishing settings and pickers."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

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
    # null clears the group's channel (the tribe's channel is used). A
    # string of digits is accepted (Discord ids don't fit a JS number).
    discord_channel_id: Optional[int] = None


class PublishableGroupSchema(HostGroupRef):
    member_count: int
    allow_alliance_posts: bool
    allow_open_fleets: bool


class DiscordChannelSchema(BaseModel):
    # Discord ids are strings: they don't fit a JavaScript number.
    id: str
    name: str
    type: str
