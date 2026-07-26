import asyncio
import logging

import discord

from .api import (
    CreateHelpTicketRequest,
    HelpTicketPanelCategory,
)
from .service import (
    create_help_ticket,
    fetch_panel_config,
    sanitize_thread_name,
)
from .views import build_close_ticket_view

logger = logging.getLogger(__name__)


async def create_ticket_from_modal(
    interaction: discord.Interaction,
    *,
    category_id: int,
    body: str,
):
    await interaction.response.defer(ephemeral=True)

    config = await asyncio.to_thread(fetch_panel_config)
    category = _find_category(config, category_id)
    if category is None:
        await interaction.followup.send(
            "That category is no longer available.",
            ephemeral=True,
        )
        return

    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.followup.send(
            "Tickets can only be opened from a text channel.",
            ephemeral=True,
        )
        return

    thread_name = sanitize_thread_name(category.code, interaction.user.name)
    try:
        thread = await interaction.channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            invitable=False,
            auto_archive_duration=10080,
            reason=f"Help ticket for {category.title}",
        )
    except discord.HTTPException as error:
        logger.exception("Failed to create help ticket thread")
        await interaction.followup.send(
            f"Could not create ticket thread: {error!s}",
            ephemeral=True,
        )
        return

    await thread.add_user(interaction.user)

    welcome_description = category.description or (
        f"Thanks for reaching out to {category.title}. "
        "Someone from the team will get back to you when they can."
    )
    welcome_embed = discord.Embed(
        title=category.title,
        description=welcome_description,
        color=0x2ECC71,
    )
    details_embed = discord.Embed(color=0x2ECC71)
    details_embed.add_field(name="Details", value=body[:1024], inline=False)

    mention = _format_mentions(category.mention_discord_ids)
    if not mention:
        logger.warning(
            "No mention targets for help category %s (%s)",
            category.id,
            category.code,
        )

    try:
        ticket = await asyncio.to_thread(
            create_help_ticket,
            CreateHelpTicketRequest(
                category_id=category.id,
                opener_discord_id=interaction.user.id,
                thread_id=thread.id,
                thread_name=thread_name,
                body=body,
            ),
        )
    except Exception:
        logger.exception("Failed to persist help ticket")
        await thread.send(
            "Your request was received, but recording the ticket failed. "
            "Please ping a moderator."
        )
        await interaction.followup.send(
            "Ticket thread created, but saving ticket metadata failed.",
            ephemeral=True,
        )
        return

    await thread.send(
        content=mention or None,
        embeds=[welcome_embed, details_embed],
        view=build_close_ticket_view(ticket.id),
    )

    await interaction.followup.send(
        f"Your ticket was opened: {thread.mention}",
        ephemeral=True,
    )


def _find_category(
    config, category_id: int
) -> HelpTicketPanelCategory | None:
    for category in config.categories:
        if category.id == category_id:
            return category
    return None


def _format_mentions(discord_ids: list[int]) -> str:
    unique_ids = list(dict.fromkeys(discord_ids))
    return " ".join(f"<@{discord_id}>" for discord_id in unique_ids)
