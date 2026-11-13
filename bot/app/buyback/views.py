"""Discord UI for hangar buyback purchase-order settlement buttons."""

from __future__ import annotations

import asyncio
import logging
import re

import discord

from app.custom_ids import (
    BUYBACK_CANCEL_PREFIX,
    BUYBACK_CANCEL_TEMPLATE,
    BUYBACK_CLOSE_PREFIX,
    BUYBACK_CLOSE_TEMPLATE,
    BUYBACK_COMPLETE_PREFIX,
    BUYBACK_COMPLETE_TEMPLATE,
    BUYBACK_CONTRACT_ACCEPTED_PREFIX,
    BUYBACK_CONTRACT_ACCEPTED_TEMPLATE,
    BUYBACK_CONTRACT_UP_PREFIX,
    BUYBACK_CONTRACT_UP_TEMPLATE,
    custom_id,
)

from .service import DiscordAckError, discord_ack_order

logger = logging.getLogger(__name__)

COMPLETE_TEMPLATE = BUYBACK_COMPLETE_TEMPLATE
CANCEL_TEMPLATE = BUYBACK_CANCEL_TEMPLATE
CONTRACT_UP_TEMPLATE = BUYBACK_CONTRACT_UP_TEMPLATE
CONTRACT_ACCEPTED_TEMPLATE = BUYBACK_CONTRACT_ACCEPTED_TEMPLATE
CLOSE_TEMPLATE = BUYBACK_CLOSE_TEMPLATE

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
    closes_thread: bool,
) -> None:
    await interaction.response.defer(ephemeral=True)

    # Complete, cancel, and Contract accepted archive the thread. Clear
    # buttons and settle interaction traffic first, then the API posts a
    # public notice, waits, and archives (same order as LP buyback
    # ISK-sent / help tickets). Do not edit or follow up in the thread
    # after the API returns — Discord unarchives on later edits.
    # Contract up leaves the thread open, so the API runs first and the
    # buttons are cleared only after it succeeds.
    if closes_thread:
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

    if closes_thread:
        return

    await _clear_message_buttons(interaction)
    await interaction.followup.send(f"{success_label}.", ephemeral=True)


class CompleteButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=COMPLETE_TEMPLATE,
):
    def __init__(self, order_id: int):
        super().__init__(
            discord.ui.Button(
                label="Complete",
                style=discord.ButtonStyle.success,
                custom_id=custom_id(BUYBACK_COMPLETE_PREFIX, order_id),
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
            closes_thread=True,
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
                custom_id=custom_id(BUYBACK_CANCEL_PREFIX, order_id),
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
            closes_thread=True,
        )


class ContractUpButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=CONTRACT_UP_TEMPLATE,
):
    def __init__(self, order_id: int):
        super().__init__(
            discord.ui.Button(
                label="Contract up",
                style=discord.ButtonStyle.success,
                custom_id=custom_id(BUYBACK_CONTRACT_UP_PREFIX, order_id),
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
            action="contract_up",
            success_label="Marked the contract up",
            closes_thread=False,
        )


class ContractAcceptedButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=CONTRACT_ACCEPTED_TEMPLATE,
):
    def __init__(self, order_id: int):
        super().__init__(
            discord.ui.Button(
                label="Contract accepted",
                style=discord.ButtonStyle.success,
                custom_id=custom_id(
                    BUYBACK_CONTRACT_ACCEPTED_PREFIX, order_id
                ),
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
            action="contract_accepted",
            success_label="Marked the contract accepted",
            closes_thread=True,
        )


class CloseButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=CLOSE_TEMPLATE,
):
    def __init__(self, order_id: int):
        super().__init__(
            discord.ui.Button(
                label="Close",
                style=discord.ButtonStyle.secondary,
                custom_id=custom_id(BUYBACK_CLOSE_PREFIX, order_id),
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
            action="close",
            success_label="Closed the sale",
            closes_thread=True,
        )


def register_buyback_buttons(client: discord.Client) -> None:
    client.add_dynamic_items(
        CompleteButton,
        CancelButton,
        ContractUpButton,
        ContractAcceptedButton,
        CloseButton,
    )
