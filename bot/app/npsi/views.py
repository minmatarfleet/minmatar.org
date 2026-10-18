"""Discord UI for NPSI Post to schedule / Pre-ping / Track buttons."""

from __future__ import annotations

import asyncio
import logging
import re

import discord

from app.custom_ids import (
    NPSI_POST_ALIAS_PREFIX,
    NPSI_POST_ALIAS_TEMPLATE,
    NPSI_POST_PREFIX,
    NPSI_POST_TEMPLATE,
    NPSI_PREPING_PREFIX,
    NPSI_PREPING_TEMPLATE,
    NPSI_TRACK_PREFIX,
    NPSI_TRACK_TEMPLATE,
    custom_id,
)
from app.settings import settings

from .service import (
    NpsiDiscordActionError,
    post_to_schedule,
    send_preping,
    start_tracking,
)

logger = logging.getLogger(__name__)

POST_TEMPLATE = NPSI_POST_TEMPLATE
POST_ALIAS_TEMPLATE = NPSI_POST_ALIAS_TEMPLATE
PREPING_TEMPLATE = NPSI_PREPING_TEMPLATE
TRACK_TEMPLATE = NPSI_TRACK_TEMPLATE


def _posted_view(event_id: int, fleet_id: int | None) -> discord.ui.View:
    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label="Pre-ping",
            style=discord.ButtonStyle.secondary,
            custom_id=custom_id(NPSI_PREPING_PREFIX, event_id),
        )
    )
    view.add_item(
        discord.ui.Button(
            label="Track",
            style=discord.ButtonStyle.success,
            custom_id=custom_id(NPSI_TRACK_PREFIX, event_id),
        )
    )
    if fleet_id:
        view.add_item(
            discord.ui.Button(
                label="Open schedule",
                style=discord.ButtonStyle.link,
                url=f"{settings.WEB_URL.rstrip('/')}/fleets/upcoming/",
            )
        )
    return view


async def _handle_action(
    interaction: discord.Interaction,
    *,
    event_id: int,
    action: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        if action == "post":
            result = await asyncio.to_thread(
                post_to_schedule,
                event_id,
                discord_user_id=interaction.user.id,
            )
        elif action == "preping":
            result = await asyncio.to_thread(
                send_preping,
                event_id,
                discord_user_id=interaction.user.id,
            )
        elif action == "track":
            result = await asyncio.to_thread(
                start_tracking,
                event_id,
                discord_user_id=interaction.user.id,
            )
        else:
            raise NpsiDiscordActionError("Unknown action.")
    except NpsiDiscordActionError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return
    except Exception:
        logger.exception(
            "NPSI discord action failed event=%s action=%s",
            event_id,
            action,
        )
        await interaction.followup.send(
            "Couldn't complete that. Try again in a bit.",
            ephemeral=True,
        )
        return

    if action == "post" and interaction.message is not None:
        try:
            await interaction.message.edit(
                content=(
                    f"Posted **{interaction.message.embeds[0].title}** to the "
                    f"fleet schedule (#{result.fleet_id}). Pre-ping when you "
                    "want pings; Track when you are in-game fleet boss."
                    if interaction.message.embeds
                    else (
                        f"Posted to the fleet schedule (#{result.fleet_id})."
                    )
                ),
                view=_posted_view(event_id, result.fleet_id),
            )
        except discord.HTTPException:
            logger.warning(
                "Posted NPSI event %s but could not update DM buttons",
                event_id,
                exc_info=True,
            )

    labels = {
        "post": f"Posted to the schedule (fleet #{result.fleet_id}).",
        "preping": "Pre-ping sent.",
        "track": "Tracking started.",
    }
    await interaction.followup.send(labels[action], ephemeral=True)


class PostToScheduleButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=POST_TEMPLATE,
):
    def __init__(self, event_id: int):
        super().__init__(
            discord.ui.Button(
                label="Post to schedule",
                style=discord.ButtonStyle.primary,
                custom_id=custom_id(NPSI_POST_PREFIX, event_id),
            )
        )
        self.event_id = event_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["event_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_action(
            interaction, event_id=self.event_id, action="post"
        )


class PrepingButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=PREPING_TEMPLATE,
):
    def __init__(self, event_id: int):
        super().__init__(
            discord.ui.Button(
                label="Pre-ping",
                style=discord.ButtonStyle.secondary,
                custom_id=custom_id(NPSI_PREPING_PREFIX, event_id),
            )
        )
        self.event_id = event_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["event_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_action(
            interaction, event_id=self.event_id, action="preping"
        )


class TrackButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=TRACK_TEMPLATE,
):
    def __init__(self, event_id: int):
        super().__init__(
            discord.ui.Button(
                label="Track",
                style=discord.ButtonStyle.success,
                custom_id=custom_id(NPSI_TRACK_PREFIX, event_id),
            )
        )
        self.event_id = event_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["event_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_action(
            interaction, event_id=self.event_id, action="track"
        )


def register_npsi_buttons(client: discord.Client) -> None:
    client.add_dynamic_items(
        PostToScheduleButton,
        PostToScheduleAliasButton,
        PrepingButton,
        TrackButton,
    )


class PostToScheduleAliasButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=POST_ALIAS_TEMPLATE,
):
    def __init__(self, event_id: int):
        super().__init__(
            discord.ui.Button(
                label="Post to schedule",
                style=discord.ButtonStyle.primary,
                custom_id=custom_id(NPSI_POST_ALIAS_PREFIX, event_id),
            )
        )
        self.event_id = event_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(int(match["event_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_action(
            interaction, event_id=self.event_id, action="post"
        )
