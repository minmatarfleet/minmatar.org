import asyncio

import discord
import requests
from discord import app_commands
from discord.ext import tasks

from app.settings import settings

from .timer_form import TimerForm
from .tickets.sync import deploy_or_update_panel
from .tickets.views import register_close_ticket_buttons
from .voicetracking_api import (
    ACTIVITY_RECORDS_URL,
    GUILDS_SYNC_URL,
    TRACKED_VOICE_CHANNELS_URL,
    CreateActivityRecordRequest,
    SyncGuildsRequest,
    SyncGuildItem,
    TrackedVoiceChannelsResponse,
)

GUILD_ID = settings.DISCORD_GUILD_ID
GUILD_IDS = [GUILD_ID]
GUILDS = [discord.Object(id=guild_id) for guild_id in GUILD_IDS]


class MyClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True
        intents.members = True
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")
        await sync_guilds_to_api()
        await deploy_or_update_panel(self)
        track_voice_channels.start()
        sync_help_ticket_panel.start()

    async def setup_hook(self) -> None:
        register_close_ticket_buttons(self)
        for guild in GUILDS:
            print(f"Syncing commands for {guild.id}")
            await self.tree.sync(guild=guild)


client = MyClient()


RAT_QUOTE_URL = f"{settings.API_URL}/reminders/rat-quote"


@client.tree.command(guilds=GUILDS, description="Submit a timer")
async def timer(interaction: discord.Interaction):
    await interaction.response.send_modal(TimerForm())


@client.tree.command(guilds=GUILDS, description="Fetch a random Rat Bible quote")
async def bible(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        response = await asyncio.to_thread(
            requests.get,
            RAT_QUOTE_URL,
            headers={"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        quote = data.get("quote", "")
        if not quote:
            await interaction.followup.send("No quote received from the Rat Bible.")
            return
        await interaction.followup.send(quote)
    except requests.RequestException as e:
        await interaction.followup.send(f"Could not fetch a Rat Bible quote: {e!s}")


def _fetch_tracked_voice_channels():
    response = requests.get(
        TRACKED_VOICE_CHANNELS_URL,
        headers={"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"},
        timeout=5,
    )
    response.raise_for_status()
    return TrackedVoiceChannelsResponse.model_validate(response.json()).channels


async def sync_guilds_to_api():
    guilds = [
        SyncGuildItem(id=guild.id, name=guild.name) for guild in client.guilds
    ]
    if not guilds:
        print("No guilds connected; skipping guild sync.")
        return

    try:
        response = await asyncio.to_thread(
            requests.post,
            GUILDS_SYNC_URL,
            json=SyncGuildsRequest(guilds=guilds).model_dump(),
            headers={"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"},
            timeout=5,
        )
        response.raise_for_status()
        print("Synced guilds to API:", response.json())
    except requests.RequestException as error:
        print("Failed to sync guilds to API: %s" % error)


@tasks.loop(seconds=60)
async def track_voice_channels():
    """Poll configured voice channels and submit minute records to the API."""
    guild = client.get_guild(int(GUILD_ID))
    if not guild:
        print(f"Guild with ID {GUILD_ID} not found.")
        return

    try:
        tracked_channels = await asyncio.to_thread(_fetch_tracked_voice_channels)
    except requests.RequestException as error:
        print("Failed to fetch tracked voice channels: %s" % error)
        return

    if not tracked_channels:
        return

    for tracked_channel in tracked_channels:
        voice_channel = guild.get_channel(tracked_channel.channel_id)
        if not voice_channel:
            print(
                "Tracked channel %s (%s) not found in guild."
                % (tracked_channel.name, tracked_channel.channel_id)
            )
            continue
        if not isinstance(
            voice_channel, (discord.VoiceChannel, discord.StageChannel)
        ):
            print(
                "Tracked channel %s (%s) is not a voice channel."
                % (tracked_channel.name, tracked_channel.channel_id)
            )
            continue
        if not voice_channel.members:
            continue

        usernames = [member.name for member in voice_channel.members]
        print(
            "Submitting voice tracking for %s users in %s"
            % (len(usernames), voice_channel.name)
        )
        try:
            response = await asyncio.to_thread(
                requests.post,
                ACTIVITY_RECORDS_URL,
                json=CreateActivityRecordRequest(
                    activity_type="voice_minute",
                    quantity=1,
                    channel_id=voice_channel.id,
                    channel_name=voice_channel.name,
                    usernames=usernames,
                ).model_dump(),
                headers={
                    "Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"
                },
                timeout=5,
            )
            response.raise_for_status()
            print(response.json())
        except requests.RequestException as error:
            print(
                "Failed to submit voice tracking for %s: %s"
                % (voice_channel.name, error)
            )


@track_voice_channels.before_loop
async def before_track_voice_channels():
    await client.wait_until_ready()


@tasks.loop(seconds=5)
async def sync_help_ticket_panel():
    await deploy_or_update_panel(client)


@sync_help_ticket_panel.before_loop
async def before_sync_help_ticket_panel():
    await client.wait_until_ready()
