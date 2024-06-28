import discord
from discord import app_commands
from app.api import (
    get_timers,
    submit_timer,
    EveStructureTimerRequest,
    EveStructureTimerResponse,
)

import traceback

# The guild in which this slash command will be registered.
# It is recommended to have a test guild to separate from your "production" bot
GUILD_IDS = [1041384161505722368]
GUILDS = [discord.Object(id=guild_id) for guild_id in GUILD_IDS]


class MyClient(discord.Client):
    def __init__(self) -> None:
        # Just default intents and a `discord.Client` instance
        # We don't need a `commands.Bot` instance because we are not
        # creating text-based commands.
        intents = discord.Intents.default()
        super().__init__(intents=intents)

        # We need an `discord.app_commands.CommandTree` instance
        # to register application commands (slash commands in this case)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

    async def setup_hook(self) -> None:
        # Sync the application command with Discord.
        for guild in GUILDS:
            print(f"Syncing commands for {guild.id}")
            await self.tree.sync(guild=guild)


class TimerForm(discord.ui.Modal, title="Timer"):
    # Our modal classes MUST subclass `discord.ui.Modal`,
    # but the title can be whatever you want.

    # This is a longer, paragraph style input, where user can submit feedback
    # Unlike the name, it is not required. If filled out, however, it will
    # only accept a maximum of 300 characters, as denoted by the
    # `max_length=300` kwarg.
    timer = discord.ui.TextInput(
        label="Paste the timer from the selected item window",
        style=discord.TextStyle.long,
        placeholder="Sosala - WATERMELLON\0\Reinforced until forever",
        required=True,
        max_length=300,
    )

    corporation_name = discord.ui.TextInput(
        label="Affiliated group",
        style=discord.TextStyle.short,
        placeholder="corporation that owns structure",
        required=False,
        max_length=64,
    )

    structure_type = discord.ui.TextInput(
        label="Structure type",
        style=discord.TextStyle.short,
        placeholder="Keepstar, Raitaru, Azbel, etc.",
        required=True,
        max_length=32,
    )

    structure_state = discord.ui.TextInput(
        label="Structure state",
        style=discord.TextStyle.short,
        placeholder="anchor, armor, hull, unanchor",
        required=True,
        max_length=32,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # lazy matching for structure state
        structure_state = self.structure_state.value.lower()
        if "anchor" in structure_state:
            structure_state = "anchoring"
        elif "armor" in structure_state:
            structure_state = "armor"
        elif "hull" in structure_state:
            structure_state = "hull"
        elif "unanchor" in structure_state:
            structure_state = "unanchoring"
        else:
            await interaction.response.send_message("Invalid state provided")
            return

        # lazy matching for structure type
        structure_type = self.structure_type.value.lower()
        if "keep" in structure_type:
            structure_type = "keepstar"
        elif "fort" in structure_type:
            structure_type = "fortizar"
        elif "astra" in structure_type:
            structure_type = "astrahus"
        elif "rait" in structure_type:
            structure_type = "raitaru"
        elif "azbel" in structure_type:
            structure_type = "azbel"
        elif "sot" in structure_type:
            structure_type = "sotiyo"
        elif "ath" in structure_type:
            structure_type = "athanor"
        elif "tat" in structure_type:
            structure_type = "tatara"
        elif "jam" in structure_type:
            structure_type = "tenebrex_cyno_jammer"
        elif "cyno" in structure_type or "beacon" in structure_type:
            structure_type = "pharolux_cyno_beacon"
        elif "gate" in structure_type or "jb" in structure_type:
            structure_type = "ansiblex_jump_gate"
        else:
            await interaction.response.send_message("Invalid type provided")
            return

        submit_timer(
            EveStructureTimerRequest(
                selected_item_window=self.timer.value,
                corporation_name=self.corporation_name.value,
                state=structure_state,
                type=structure_type,
            )
        )
        await interaction.response.send_message("Timer submitted!")

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            "Oops! Something went wrong.", ephemeral=True
        )

        # Make sure we know what the error actually is
        traceback.print_exception(type(error), error, error.__traceback__)


client = MyClient()


@client.tree.command(guilds=GUILDS, description="Submit a timer")
async def timer(interaction: discord.Interaction):
    # Send the modal with an instance of our `Feedback` class
    # Since modals require an interaction, they cannot be done as a response to a text command.
    # They can only be done as a response to either an application command or a button press.
    await interaction.response.send_modal(TimerForm())
