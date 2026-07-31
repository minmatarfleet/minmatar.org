"""Discord UI for notification Mark as read buttons."""

from __future__ import annotations

import asyncio
import logging
import re

import discord

from .service import ack_delivery

logger = logging.getLogger(__name__)

NOTIF_ACK_TEMPLATE = r"notif_ack:(?P<delivery_id>[0-9]+)"


class MarkAsReadButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=NOTIF_ACK_TEMPLATE,
):
    def __init__(self, delivery_id: int):
        super().__init__(
            discord.ui.Button(
                label="Mark as read",
                style=discord.ButtonStyle.secondary,
                custom_id=f"notif_ack:{delivery_id}",
            )
        )
        self.delivery_id = delivery_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["delivery_id"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await asyncio.to_thread(
                ack_delivery,
                self.delivery_id,
                interaction.user.id,
            )
        except Exception:
            logger.exception(
                "Failed to ack notification delivery %s", self.delivery_id
            )
            await interaction.followup.send(
                "Couldn't mark that as read. Try again in a bit.",
                ephemeral=True,
            )
            return

        if result.delete_message and interaction.message is not None:
            try:
                await interaction.message.delete()
            except discord.HTTPException:
                logger.warning(
                    "Acked delivery %s but could not delete DM message",
                    self.delivery_id,
                    exc_info=True,
                )
                await interaction.followup.send(
                    "Marked as read.",
                    ephemeral=True,
                )
                return

        # Message deleted — ephemeral followup still works in DMs.
        try:
            await interaction.followup.send(
                "Marked as read.",
                ephemeral=True,
            )
        except discord.HTTPException:
            pass


def register_notification_buttons(client: discord.Client) -> None:
    client.add_dynamic_items(MarkAsReadButton)
