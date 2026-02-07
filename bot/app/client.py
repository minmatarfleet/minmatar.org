import asyncio

import discord
import requests
from discord import app_commands
from discord.ext import tasks

from app.settings import settings

from .standing_api import STANDING_URL, CreateStandingFleetTrackingRequest
from .timer_form import TimerForm

# The guild in which this slash command will be registered.
# It is recommended to have a test guild to separate from your "production" bot
GUILD_ID = settings.DISCORD_GUILD_ID
GUILD_IDS = [GUILD_ID]
GUILDS = [discord.Object(id=guild_id) for guild_id in GUILD_IDS]
DISCORD_STANDINGFLEET_VOICE_CHANNEL_ID = settings.DISCORD_STANDINGFLEET_VOICE_CHANNEL_ID

class MyClient(discord.Client):
    def __init__(self) -> None:
        # Just default intents and a `discord.Client` instance
        # We don't need a `commands.Bot` instance because we are not
        # creating text-based commands.
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True  # Needed to access voice state information
        intents.members = True  # Needed to access member information
        super().__init__(intents=intents)

        # We need an `discord.app_commands.CommandTree` instance
        # to register application commands (slash commands in this case)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")
        check_standing_fleet_channel.start()

    async def setup_hook(self) -> None:
        # Sync the application command with Discord.
        for guild in GUILDS:
            print(f"Syncing commands for {guild.id}")
            await self.tree.sync(guild=guild)


client = MyClient()


RAT_QUOTE_URL = f"{settings.API_URL}/reminders/rat-quote"


@client.tree.command(guilds=GUILDS, description="Submit a timer")
async def timer(interaction: discord.Interaction):
    # Send the modal with an instance of our `Feedback` class
    # Since modals require an interaction, they cannot be done as a response to a text command.
    # They can only be done as a response to either an application command or a button press.
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


@tasks.loop(seconds=60)
async def check_standing_fleet_channel():
    """
    Fetches the members in standing fleet voice channel and submits
    to the API for tracking
    """

    voice_channel_id = DISCORD_STANDINGFLEET_VOICE_CHANNEL_ID
    guild = client.get_guild(GUILD_ID)
    if guild:
        voice_channel = guild.get_channel(voice_channel_id)
        if not voice_channel:
            print(f"Channel with ID {voice_channel_id} not found.")
            return
        if not isinstance(voice_channel, discord.VoiceChannel):
            print(f"Channel with ID {voice_channel_id} is not a voice channel.")
            return
        if not voice_channel.members:
            print(f"No members in {voice_channel.name} currently.")
            return
        members = voice_channel.members
        usernames = [member.name for member in members]
        print("Submitting standing fleet tracking for %s users" % len(usernames))
        response = requests.post(
            STANDING_URL,
            json=CreateStandingFleetTrackingRequest(
                minutes=1, usernames=usernames
            ).model_dump(),
            headers={"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"},
            timeout=2,
        )
        print(response.json())
        print("Submitted standing fleet tracking")


@check_standing_fleet_channel.before_loop
async def before_check():
    """Wait until the bot is ready before starting the task."""
    await client.wait_until_ready()
