import discord


class HelpRequestModal(discord.ui.Modal, title="Help request"):
    def __init__(self, category_id: int):
        super().__init__()
        self.category_id = category_id

    details = discord.ui.TextInput(
        label="Details",
        style=discord.TextStyle.long,
        placeholder="Describe what you need help with...",
        required=True,
        max_length=2000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # pylint: disable=import-outside-toplevel
        from .ticket_flow import create_ticket_from_modal

        await create_ticket_from_modal(
            interaction,
            category_id=self.category_id,
            body=self.details.value,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(
                "Something went wrong opening your ticket.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Something went wrong opening your ticket.",
                ephemeral=True,
            )
        raise error
