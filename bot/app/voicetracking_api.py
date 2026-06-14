from pydantic import BaseModel

from app.settings import settings

ACTIVITY_RECORDS_URL = f"{settings.API_URL}/discord/activity/records"
GUILDS_SYNC_URL = f"{settings.API_URL}/discord/guilds/sync"
TRACKED_VOICE_CHANNELS_URL = (
    f"{settings.API_URL}/discord/voicetracking/channels"
)


class SyncGuildItem(BaseModel):
    id: int
    name: str


class SyncGuildsRequest(BaseModel):
    guilds: list[SyncGuildItem]


class CreateActivityRecordRequest(BaseModel):
    activity_type: str
    quantity: int
    channel_id: int
    channel_name: str
    usernames: list[str]


class ActivityRecordResponse(BaseModel):
    ids: list[int]


class TrackedVoiceChannelResponse(BaseModel):
    channel_id: int
    name: str


class TrackedVoiceChannelsResponse(BaseModel):
    channels: list[TrackedVoiceChannelResponse]
