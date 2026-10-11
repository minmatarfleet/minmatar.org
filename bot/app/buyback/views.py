"""Discord UI for hangar buyback purchase-order Complete/Cancel buttons."""

from __future__ import annotations

import asyncio
import logging
import re

import discord

from .service import DiscordAckError, discord_ack_order

logger = logging.getLogger(__name__)

COMPLETE_TEMPLATE = r"buyback:complete:(?P<order_id>[0-9]+)"
CANCEL_TEMPLATE = r"buyback:cancel:(?P<order_id>[0-9]+)"

THREAD_ARCHIVE_DELAY_SECONDS = 5


async def _clear_message_buttons(interaction: discord.Interaction) -> None:
    if interaction.message is None:
        return
    try:
        await interaction.message.edit(view=None)
    except discord.HTTPException:
        logger.warning(
            "Could not clear hangar buyback message buttons",
            exc_info=True,
        )


async def _handle_ack(
    interaction: discord.Interaction,
    *,
    order_id: int,
    action: str,
    success_label: str,
) -> None:
    await interaction.response.defer(ephemeral=True)

    # Complete/cancel archives the thread. Clear buttons and settle
    # interaction traffic first, then the API posts a public notice, waits,
    # and archives (same order as LP buyback ISK-sent / help tickets).
    # Do not edit or follow up in the thread after the API returns —
    # Discord unarchives on later edits.
    await _clear_message_buttons(interaction)
    await interaction.followup.send(f"{success_label}.", ephemeral=True)
    await asyncio.sleep(THREAD_ARCHIVE_DELAY_SECONDS)

    try:
        await asyncio.to_thread(
            discord_ack_order,
            order_id,
            action=action,
            discord_user_id=interaction.user.id,
        )
    except DiscordAckError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return
    except Exception:
        logger.exception(
            "Failed hangar buyback discord-ack order=%s action=%s",
            order_id,
            action,
        )
        await interaction.followup.send(
            "Couldn't record that acknowledgment. Try again in a bit.",
            ephemeral=True,
        )
        return


class CompleteButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=COMPLETE_TEMPLATE,
):
    def __init__(self, order_id: int):
        super().__init__(
            discord.ui.Button(
                label="Complete",
                style=discord.ButtonStyle.success,
                custom_id=f"buyback:complete:{order_id}",
            )
        )
        self.order_id = order_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["order_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_ack(
            interaction,
            order_id=self.order_id,
            action="complete",
            success_label="Marked sale as complete",
        )


class CancelButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=CANCEL_TEMPLATE,
):
    def __init__(self, order_id: int):
        super().__init__(
            discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.danger,
                custom_id=f"buyback:cancel:{order_id}",
            )
        )
        self.order_id = order_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["order_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_ack(
            interaction,
            order_id=self.order_id,
            action="cancel",
            success_label="Cancelled the sale",
        )


def register_buyback_buttons(client: discord.Client) -> None:
    client.add_dynamic_items(CompleteButton, CancelButton)
