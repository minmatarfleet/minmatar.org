"""Discord UI for Appoint / Not now on the executor's chief-volunteer DMs."""

from __future__ import annotations

import asyncio
import logging
import re

import discord

from app.custom_ids import (
    TRIBE_CHIEF_APPOINT_PREFIX,
    TRIBE_CHIEF_APPOINT_TEMPLATE,
    TRIBE_CHIEF_DECLINE_PREFIX,
    TRIBE_CHIEF_DECLINE_TEMPLATE,
    custom_id,
)

from .service import ChiefActionError, answer_volunteer

logger = logging.getLogger(__name__)


async def _answer(
    interaction: discord.Interaction,
    volunteer_id: int,
    action: str,
    done: str,
):
    await interaction.response.defer(ephemeral=True)
    try:
        # The API edits this DM once the answer is saved.
        await asyncio.to_thread(
            answer_volunteer, volunteer_id, action, interaction.user.id
        )
    except ChiefActionError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return
    except Exception:
        logger.exception(
            "Failed to %s chief volunteer %s", action, volunteer_id
        )
        await interaction.followup.send(
            "Couldn't save that. Try again in a bit.", ephemeral=True
        )
        return
    await interaction.followup.send(done, ephemeral=True)


class AppointChiefButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=TRIBE_CHIEF_APPOINT_TEMPLATE,
):
    def __init__(self, volunteer_id: int):
        super().__init__(
            discord.ui.Button(
                label="Appoint as chief",
                style=discord.ButtonStyle.success,
                custom_id=custom_id(TRIBE_CHIEF_APPOINT_PREFIX, volunteer_id),
            )
        )
        self.volunteer_id = volunteer_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["volunteer_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _answer(interaction, self.volunteer_id, "appoint", "Appointed.")


class DeclineChiefButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=TRIBE_CHIEF_DECLINE_TEMPLATE,
):
    def __init__(self, volunteer_id: int):
        super().__init__(
            discord.ui.Button(
                label="Not now",
                style=discord.ButtonStyle.secondary,
                custom_id=custom_id(TRIBE_CHIEF_DECLINE_PREFIX, volunteer_id),
            )
        )
        self.volunteer_id = volunteer_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["volunteer_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _answer(
            interaction,
            self.volunteer_id,
            "decline",
            "Not now. The seat stays open.",
        )


def register_tribe_chief_buttons(client: discord.Client) -> None:
    client.add_dynamic_items(AppointChiefButton, DeclineChiefButton)
