"""Schemas for tribe group events."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from tribes.endpoints.groups.schemas import CharacterRefSchema
from tribes.schemas import HostGroupRef


class EventRecurrence(str, Enum):
    NONE = "none"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class EventWhereKind(str, Enum):
    VOICE = "voice"
    PLACE = "place"


class EventStatus(str, Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TribeEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    starts_at: datetime
    ends_at: Optional[datetime] = None
    recurrence: EventRecurrence = EventRecurrence.NONE
    where_kind: EventWhereKind = EventWhereKind.VOICE
    # A string of digits is accepted (Discord ids don't fit a JS number).
    voice_channel_id: Optional[int] = None
    location: str = Field(default="", max_length=200)
    members_only: bool = False
    announce: bool = True


class TribeEventPatch(BaseModel):
    """Every field optional; left out means unchanged."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    recurrence: Optional[EventRecurrence] = None
    where_kind: Optional[EventWhereKind] = None
    voice_channel_id: Optional[int] = None
    location: Optional[str] = Field(default=None, max_length=200)
    members_only: Optional[bool] = None


class TribeEventSchema(BaseModel):
    id: int
    tribe_group: HostGroupRef
    created_by: Optional[CharacterRefSchema] = None
    title: str
    description: str
    starts_at: datetime
    ends_at: Optional[datetime] = None
    recurrence: EventRecurrence
    recurrence_label: str
    where_kind: EventWhereKind
    # Discord ids are strings: they don't fit a JavaScript number.
    voice_channel_id: Optional[str] = None
    voice_channel_name: str = ""
    location: str = ""
    where_label: str
    members_only: bool
    announce: bool
    discord_event_id: Optional[str] = None
    discord_event_url: Optional[str] = None
    interested_count: int = 0
    status: EventStatus
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    can_manage: bool = False


class TribeEventPreviewSchema(BaseModel):
    title: str
    starts_at: datetime
    where_label: str
    recurrence_label: str


class TribeEventAnnouncementPreview(BaseModel):
    """The announcement exactly as the bot would post it (the event link
    is a placeholder until Discord creates the event)."""

    channel_name: Optional[str] = None
    content: Optional[str] = None
    event_preview: TribeEventPreviewSchema
