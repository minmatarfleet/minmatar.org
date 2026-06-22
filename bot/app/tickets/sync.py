import asyncio
import logging

import discord
from discord import NotFound

from app.settings import settings

from .api import HelpTicketPanelStateUpdate
from .panel import build_panel_embed, build_panel_view, register_help_ticket_panel_view
from .service import (
    fetch_panel_config,
    fetch_panel_state,
    update_panel_state,
)

logger = logging.getLogger(__name__)


async def deploy_or_update_panel(client: discord.Client) -> None:
    help_channel_id = settings.DISCORD_HELP_CHANNEL_ID
    if not help_channel_id:
        logger.info("DISCORD_HELP_CHANNEL_ID unset; skipping help ticket panel sync.")
        return

    try:
        config = await asyncio.to_thread(fetch_panel_config)
        state = await asyncio.to_thread(fetch_panel_state)
    except Exception:
        logger.exception("Failed to fetch help ticket panel config/state")
        return

    if not config.categories:
        logger.info("No help ticket categories configured; skipping panel.")
        return

    channel = client.get_channel(int(help_channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(help_channel_id))
        except NotFound:
            logger.error("Help channel %s not found.", help_channel_id)
            return

    if not isinstance(channel, discord.TextChannel):
        logger.error("Help channel %s is not a text channel.", help_channel_id)
        return

    embed = build_panel_embed(config)
    view = build_panel_view(config)
    register_help_ticket_panel_view(client)

    if state.message_id is not None and state.content_hash == config.hash:
        logger.info("Help ticket panel unchanged; skipping edit.")
        return

    if state.message_id is not None:
        try:
            message = await channel.fetch_message(state.message_id)
            await message.edit(embed=embed, view=view)
            await asyncio.to_thread(
                update_panel_state,
                HelpTicketPanelStateUpdate(
                    channel_id=channel.id,
                    message_id=message.id,
                    content_hash=config.hash,
                ),
            )
            logger.info("Updated help ticket panel message %s", message.id)
            return
        except NotFound:
            logger.warning(
                "Help ticket panel message %s missing; creating a new one.",
                state.message_id,
            )
        except discord.HTTPException:
            logger.exception(
                "Failed to edit help ticket panel message %s", state.message_id
            )
            return

    message = await channel.send(embed=embed, view=view)
    await asyncio.to_thread(
        update_panel_state,
        HelpTicketPanelStateUpdate(
            channel_id=channel.id,
            message_id=message.id,
            content_hash=config.hash,
        ),
    )
    logger.info("Posted help ticket panel message %s", message.id)
