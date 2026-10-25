"""Discord UI for the Sitting out and Stop fleet invites buttons on fleet
invite DMs."""

from __future__ import annotations

import asyncio
import logging
import re

import discord

from app.custom_ids import (
    FLEET_INVITE_OUT_PREFIX,
    FLEET_INVITE_OUT_TEMPLATE,
    FLEET_INVITE_STOP_PREFIX,
    FLEET_INVITE_STOP_TEMPLATE,
    custom_id,
)

from app.settings import settings

from .service import SitOutError, sit_out, stop_invites

logger = logging.getLogger(__name__)

ACCOUNT_URL = f"{settings.WEB_URL}/account/#notifications"


class SitOutButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=FLEET_INVITE_OUT_TEMPLATE,
):
    def __init__(self, invite_id: int):
        super().__init__(
            discord.ui.Button(
                label="Sitting out",
                style=discord.ButtonStyle.secondary,
                custom_id=custom_id(FLEET_INVITE_OUT_PREFIX, invite_id),
            )
        )
        self.invite_id = invite_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["invite_id"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            # The API edits this DM once the answer is saved.
            await asyncio.to_thread(
                sit_out, self.invite_id, interaction.user.id
            )
        except SitOutError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception(
                "Failed to sit out fleet invite %s", self.invite_id
            )
            await interaction.followup.send(
                "Couldn't save that. Try again in a bit.", ephemeral=True
            )
            return
        # The API edits the DM; a private fleet's edit repeats the opsec line.
        await interaction.followup.send(
            "Got it, you're sitting this one out.", ephemeral=True
        )


class StopInvitesButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=FLEET_INVITE_STOP_TEMPLATE,
):
    def __init__(self, invite_id: int):
        super().__init__(
            discord.ui.Button(
                label="Stop fleet invites",
                style=discord.ButtonStyle.secondary,
                custom_id=custom_id(FLEET_INVITE_STOP_PREFIX, invite_id),
            )
        )
        self.invite_id = invite_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["invite_id"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await asyncio.to_thread(
                stop_invites, self.invite_id, interaction.user.id
            )
        except SitOutError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception(
                "Failed to stop fleet invites from invite %s", self.invite_id
            )
            await interaction.followup.send(
                "Couldn't save that. Try again in a bit.", ephemeral=True
            )
            return
        await interaction.followup.send(
            "Fleet invites are off. FCs won't DM you fleet invites any "
            "more; you still see every fleet on the schedule. Turn them "
            f"back on in Account › Notifications: {ACCOUNT_URL}",
            ephemeral=True,
        )


def register_fleet_invite_buttons(client: discord.Client) -> None:
    client.add_dynamic_items(SitOutButton, StopInvitesButton)
