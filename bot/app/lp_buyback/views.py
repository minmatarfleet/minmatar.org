"""Discord UI for LP buyback settlement ack buttons."""

from __future__ import annotations

import asyncio
import logging
import re

import discord

from .service import DiscordAckError, discord_ack_order

logger = logging.getLogger(__name__)

LP_SENT_TEMPLATE = r"lp_buyback:lp:(?P<order_id>[0-9]+)"
ISK_SENT_TEMPLATE = r"lp_buyback:isk:(?P<order_id>[0-9]+)"

# Match help tickets: settle interaction traffic before archiving so Discord
# does not unarchive the thread when a followup/edit lands after close.
THREAD_ARCHIVE_DELAY_SECONDS = 5


async def _clear_message_buttons(interaction: discord.Interaction) -> None:
    if interaction.message is None:
        return
    try:
        await interaction.message.edit(view=None)
    except discord.HTTPException:
        logger.warning(
            "Could not clear LP buyback message buttons",
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

    # ISK sent: clear buttons + settle interaction traffic, then the API posts
    # a public "ISK sent" notice, waits, and archives (same delay as help
    # tickets). Do not edit/followup the thread after the API returns.
    closes_thread = action == "isk_sent"
    if closes_thread:
        await _clear_message_buttons(interaction)
        await interaction.followup.send(f"{success_label}.", ephemeral=True)
        await asyncio.sleep(THREAD_ARCHIVE_DELAY_SECONDS)

    try:
        result = await asyncio.to_thread(
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
            "Failed LP buyback discord-ack order=%s action=%s",
            order_id,
            action,
        )
        await interaction.followup.send(
            "Couldn't record that acknowledgment. Try again in a bit.",
            ephemeral=True,
        )
        return

    if closes_thread:
        return

    await _clear_message_buttons(interaction)
    await interaction.followup.send(
        f"{success_label} (status: {result.status}).",
        ephemeral=True,
    )


class LpSentButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=LP_SENT_TEMPLATE,
):
    def __init__(self, order_id: int):
        super().__init__(
            discord.ui.Button(
                label="LP sent",
                style=discord.ButtonStyle.success,
                custom_id=f"lp_buyback:lp:{order_id}",
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
            action="lp_sent",
            success_label="Marked LP as sent",
        )


class IskSentButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=ISK_SENT_TEMPLATE,
):
    def __init__(self, order_id: int):
        super().__init__(
            discord.ui.Button(
                label="ISK sent",
                style=discord.ButtonStyle.success,
                custom_id=f"lp_buyback:isk:{order_id}",
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
            action="isk_sent",
            success_label="Marked ISK as sent",
        )


def register_lp_buyback_buttons(client: discord.Client) -> None:
    client.add_dynamic_items(LpSentButton, IskSentButton)
