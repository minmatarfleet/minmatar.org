from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer
from discord.channels import VOICE_TRACKING_CHANNEL_TYPES
from discord.guilds import sync_discord_guilds
from discord.models import DiscordChannel, DiscordChannelActivityRecord

router = Router(tags=["Discord"])


class SyncGuildItem(BaseModel):
    id: int
    name: str


class SyncGuildsRequest(BaseModel):
    guilds: list[SyncGuildItem]


class SyncGuildsResponse(BaseModel):
    synced: int


class CreateActivityRecordRequest(BaseModel):
    activity_type: str
    quantity: int
    channel_id: int
    channel_name: str
    usernames: list[str]


class CreateVoiceTrackingRequest(BaseModel):
    minutes: int
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


@router.post(
    "/guilds/sync",
    response=SyncGuildsResponse,
    auth=AuthBearer(),
)
def sync_guilds_from_bot(request, payload: SyncGuildsRequest):
    synced = sync_discord_guilds(
        source_guilds=[
            {"id": guild.id, "name": guild.name} for guild in payload.guilds
        ]
    )
    return {"synced": synced}


@router.get(
    "/voicetracking/channels",
    response=TrackedVoiceChannelsResponse,
    auth=AuthBearer(),
)
def get_tracked_voice_channels(request):
    channels = DiscordChannel.objects.filter(
        track_voice_activity=True,
        channel_type__in=VOICE_TRACKING_CHANNEL_TYPES,
    ).order_by("name")
    return {
        "channels": [
            {"channel_id": channel.channel_id, "name": channel.name}
            for channel in channels
        ]
    }


def _is_voice_minute_allowed(channel_id: int) -> bool:
    return DiscordChannel.objects.filter(
        channel_id=channel_id,
        track_voice_activity=True,
        channel_type__in=VOICE_TRACKING_CHANNEL_TYPES,
    ).exists()


@router.post(
    "/activity/records",
    response=ActivityRecordResponse,
    auth=AuthBearer(),
)
def create_activity_records(request, payload: CreateActivityRecordRequest):
    valid_types = {
        choice[0]
        for choice in DiscordChannelActivityRecord.ACTIVITY_TYPE_CHOICES
    }
    if payload.activity_type not in valid_types:
        return {"ids": []}

    if payload.activity_type == DiscordChannelActivityRecord.VOICE_MINUTE:
        if not _is_voice_minute_allowed(payload.channel_id):
            return {"ids": []}
    elif payload.activity_type == DiscordChannelActivityRecord.TEXT_MESSAGE:
        return {"ids": []}

    records = DiscordChannelActivityRecord.objects.bulk_create(
        [
            DiscordChannelActivityRecord(
                activity_type=payload.activity_type,
                username=username,
                quantity=payload.quantity,
                channel_id=payload.channel_id,
                channel_name=payload.channel_name,
            )
            for username in payload.usernames
        ]
    )
    return {"ids": [record.id for record in records]}


@router.post(
    "/voicetracking/records",
    response=ActivityRecordResponse,
    auth=AuthBearer(),
)
def create_voice_tracking_records(
    request, payload: CreateVoiceTrackingRequest
):
    return create_activity_records(
        request,
        CreateActivityRecordRequest(
            activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
            quantity=payload.minutes,
            channel_id=payload.channel_id,
            channel_name=payload.channel_name,
            usernames=payload.usernames,
        ),
    )
