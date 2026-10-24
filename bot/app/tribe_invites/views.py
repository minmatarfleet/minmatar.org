"""Discord UI for the Decline button on tribe invite DMs."""

from __future__ import annotations

import asyncio
import logging
import re

import discord

from app.custom_ids import (
    TRIBE_INVITE_DECLINE_PREFIX,
    TRIBE_INVITE_DECLINE_TEMPLATE,
    custom_id,
)

from .service import DeclineError, decline_invitation

logger = logging.getLogger(__name__)


class DeclineInviteButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=TRIBE_INVITE_DECLINE_TEMPLATE,
):
    def __init__(self, invitation_id: int):
        super().__init__(
            discord.ui.Button(
                label="Decline",
                style=discord.ButtonStyle.secondary,
                custom_id=custom_id(
                    TRIBE_INVITE_DECLINE_PREFIX, invitation_id
                ),
            )
        )
        self.invitation_id = invitation_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["invitation_id"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            # The API edits this DM once the decline is saved.
            await asyncio.to_thread(
                decline_invitation,
                self.invitation_id,
                interaction.user.id,
            )
        except DeclineError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception(
                "Failed to decline tribe invite %s", self.invitation_id
            )
            await interaction.followup.send(
                "Couldn't decline that invite. Try again in a bit.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            "Declined. The chief has been told.", ephemeral=True
        )


def register_tribe_invite_buttons(client: discord.Client) -> None:
    client.add_dynamic_items(DeclineInviteButton)
