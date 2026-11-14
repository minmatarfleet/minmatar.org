"""Discord UI for the I'm available, I'm not available and Stop fleet
invites buttons on fleet invite DMs (docs/fleets/invite-rsvp.md)."""

from __future__ import annotations

import asyncio
import logging
import re

import discord

from app.custom_ids import (
    FLEET_INVITE_IN_PREFIX,
    FLEET_INVITE_IN_TEMPLATE,
    FLEET_INVITE_OUT_PREFIX,
    FLEET_INVITE_OUT_TEMPLATE,
    FLEET_INVITE_STOP_PREFIX,
    FLEET_INVITE_STOP_TEMPLATE,
    custom_id,
)

from app.settings import settings

from .service import SitOutError, sign_up_link, sit_out, stop_invites

logger = logging.getLogger(__name__)

ACCOUNT_URL = f"{settings.WEB_URL}/account/#notifications"


class AvailableButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=FLEET_INVITE_IN_TEMPLATE,
):
    """I'm available: Discord says who pressed it, so the link the bot
    hands back can only be for the invited pilot."""

    def __init__(self, invite_id: int):
        super().__init__(
            discord.ui.Button(
                label="I'm available",
                style=discord.ButtonStyle.success,
                custom_id=custom_id(FLEET_INVITE_IN_PREFIX, invite_id),
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
            url = await asyncio.to_thread(
                sign_up_link, self.invite_id, interaction.user.id
            )
        except SitOutError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception(
                "Failed to make a sign-up link for invite %s", self.invite_id
            )
            await interaction.followup.send(
                "Couldn't open the sign-up form. Try again in a bit.",
                ephemeral=True,
            )
            return
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Open the picker", url=url))
        await interaction.followup.send(
            "Pick your ships and sign up. You're not signed up until you "
            "press Sign up on the page.\n-# Works for 10 minutes, only for "
            "you.",
            view=view,
            ephemeral=True,
        )


class SitOutButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=FLEET_INVITE_OUT_TEMPLATE,
):
    def __init__(self, invite_id: int):
        super().__init__(
            discord.ui.Button(
                label="I'm not available",
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
            "Got it, you're not available for this one. You'll still get "
            "invites to future fleets.",
            ephemeral=True,
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
    client.add_dynamic_items(
        AvailableButton, SitOutButton, StopInvitesButton
    )
