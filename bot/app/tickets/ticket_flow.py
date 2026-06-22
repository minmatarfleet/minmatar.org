import asyncio
import logging

import discord

from .api import (
    CloseHelpTicketRequest,
    CreateHelpTicketRequest,
    HelpTicketPanelCategory,
)
from .service import (
    close_help_ticket,
    create_help_ticket,
    fetch_help_ticket,
    fetch_panel_config,
    member_can_close_ticket,
    sanitize_thread_name,
)
from .views import CloseTicketView

logger = logging.getLogger(__name__)

THREAD_ARCHIVE_DELAY_SECONDS = 5


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

    close_view = CloseTicketView(ticket.id)
    interaction.client.add_view(close_view)

    await thread.send(
        content=mention or None,
        embeds=[welcome_embed, details_embed],
        view=close_view,
    )

    await interaction.followup.send(
        f"Your ticket was opened: {thread.mention}",
        ephemeral=True,
    )


async def _send_close_notice_dm(
    client: discord.Client,
    *,
    opener_discord_id: int,
    closed_by: discord.Member,
    close_reason: str,
) -> None:
    reason_text = close_reason.strip() or "No reason specified"
    try:
        opener = await client.fetch_user(opener_discord_id)
        await opener.send(
            f"Your help ticket has been closed by {closed_by.display_name}.\n"
            f"**Reason:** {reason_text}"
        )
    except discord.HTTPException:
        logger.warning(
            "Could not DM opener %s about closed help ticket",
            opener_discord_id,
            exc_info=True,
        )


async def close_ticket(
    interaction: discord.Interaction,
    ticket_id: int,
    *,
    close_reason: str = "",
):
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "Unable to verify your permissions.",
            ephemeral=True,
        )
        return

    if not member_can_close_ticket(interaction.user):
        await interaction.response.send_message(
            "Only moderators and administrators can close tickets.",
            ephemeral=True,
        )
        return

    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "Tickets can only be closed from the ticket thread.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    reason_text = close_reason.strip() or "No reason specified"

    try:
        ticket = await asyncio.to_thread(fetch_help_ticket, ticket_id)
    except Exception:
        logger.exception("Failed to fetch help ticket %s", ticket_id)
        await interaction.followup.send(
            "Could not load ticket details. Try again.",
            ephemeral=True,
        )
        return

    await interaction.followup.send("Ticket closed.", ephemeral=True)
    await asyncio.sleep(THREAD_ARCHIVE_DELAY_SECONDS)

    try:
        await asyncio.to_thread(
            close_help_ticket,
            ticket_id,
            CloseHelpTicketRequest(
                closed_by_discord_id=interaction.user.id,
                close_reason=close_reason,
            ),
        )
    except Exception:
        logger.exception("Failed to close help ticket %s via API", ticket_id)
        await interaction.followup.send(
            "Could not archive the Discord thread. The ticket is still open.",
            ephemeral=True,
        )
        return

    await _send_close_notice_dm(
        interaction.client,
        opener_discord_id=ticket.opener_discord_id,
        closed_by=interaction.user,
        close_reason=reason_text,
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


async def register_persistent_ticket_views(client: discord.Client):
    # pylint: disable=import-outside-toplevel
    from .service import fetch_open_help_tickets

    try:
        open_tickets = await asyncio.to_thread(fetch_open_help_tickets)
    except Exception:
        logger.exception("Failed to fetch open help tickets for view registration")
        return

    for ticket in open_tickets.tickets:
        client.add_view(CloseTicketView(ticket.id))
