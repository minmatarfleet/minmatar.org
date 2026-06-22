import discord


class CloseWithReasonModal(discord.ui.Modal, title="Close ticket"):
    def __init__(self, ticket_id: int):
        super().__init__()
        self.ticket_id = ticket_id

    reason = discord.ui.TextInput(
        label="Reason",
        style=discord.TextStyle.long,
        placeholder="Why is this ticket being closed?",
        required=False,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # pylint: disable=import-outside-toplevel
        from .ticket_flow import close_ticket

        await close_ticket(
            interaction,
            self.ticket_id,
            close_reason=self.reason.value,
        )


class CloseTicketView(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

        close_button = discord.ui.Button(
            label="Close",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=f"help_ticket_close:{ticket_id}",
        )
        close_button.callback = self.close_callback
        self.add_item(close_button)

        close_with_reason_button = discord.ui.Button(
            label="Close With Reason",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=f"help_ticket_close_reason:{ticket_id}",
        )
        close_with_reason_button.callback = self.close_with_reason_callback
        self.add_item(close_with_reason_button)

    async def close_callback(self, interaction: discord.Interaction):
        # pylint: disable=import-outside-toplevel
        from .ticket_flow import close_ticket

        await close_ticket(interaction, self.ticket_id)

    async def close_with_reason_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            CloseWithReasonModal(self.ticket_id)
        )
