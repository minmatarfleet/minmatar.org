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


async def _handle_ack(
    interaction: discord.Interaction,
    *,
    order_id: int,
    action: str,
    success_label: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
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

    if interaction.message is not None:
        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            logger.warning(
                "Acked order %s but could not clear message buttons",
                order_id,
                exc_info=True,
            )

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
