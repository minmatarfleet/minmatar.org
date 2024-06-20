import discord
from discord import app_commands

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
        placeholder="Type your feedback here...",
        required=True,
        max_length=300,
    )

    affiliated_group = discord.ui.TextInput(
        label="Affiliated group",
        style=discord.TextStyle.long,
        placeholder="Corporation, alliance, or ticker",
        required=False,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        print(self.timer)
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
