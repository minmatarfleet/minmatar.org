import re

import discord

from .close_flow import close_ticket


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
        await close_ticket(
            interaction,
            self.ticket_id,
            close_reason=self.reason.value,
        )


class CloseTicketButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"help_ticket_close:(?P<ticket_id>[0-9]+)",
):
    def __init__(self, ticket_id: int):
        super().__init__(
            discord.ui.Button(
                label="Close",
                style=discord.ButtonStyle.danger,
                emoji="🔒",
                custom_id=f"help_ticket_close:{ticket_id}",
            )
        )
        self.ticket_id = ticket_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["ticket_id"]))

    async def callback(self, interaction: discord.Interaction):
        await close_ticket(interaction, self.ticket_id)


class CloseWithReasonButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"help_ticket_close_reason:(?P<ticket_id>[0-9]+)",
):
    def __init__(self, ticket_id: int):
        super().__init__(
            discord.ui.Button(
                label="Close With Reason",
                style=discord.ButtonStyle.danger,
                emoji="🔒",
                custom_id=f"help_ticket_close_reason:{ticket_id}",
            )
        )
        self.ticket_id = ticket_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["ticket_id"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            CloseWithReasonModal(self.ticket_id)
        )


def build_close_ticket_view(ticket_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(CloseTicketButton(ticket_id))
    view.add_item(CloseWithReasonButton(ticket_id))
    return view


def register_close_ticket_buttons(client: discord.Client) -> None:
    client.add_dynamic_items(CloseTicketButton, CloseWithReasonButton)
