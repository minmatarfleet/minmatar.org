import asyncio
import logging

import discord

from .api import CloseHelpTicketRequest
from .service import (
    close_help_ticket,
    fetch_help_ticket,
    member_can_close_ticket,
)

logger = logging.getLogger(__name__)

THREAD_ARCHIVE_DELAY_SECONDS = 5


async def _can_close_ticket(
    member: discord.Member,
    thread: discord.Thread,
    opener_discord_id: int,
) -> bool:
    """Moderators/admins, the ticket opener, and anyone participating in
    the ticket thread (e.g. the tribe owner or mentioned team members)
    may close the ticket."""
    if member_can_close_ticket(member):
        return True
    if member.id == opener_discord_id:
        return True
    try:
        await thread.fetch_member(member.id)
    except discord.NotFound:
        return False
    except discord.HTTPException:
        logger.exception(
            "Failed to check thread membership for %s in %s",
            member.id,
            thread.id,
        )
        return False
    return True


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

    if not await _can_close_ticket(
        interaction.user,
        interaction.channel,
        ticket.opener_discord_id,
    ):
        await interaction.followup.send(
            "Only moderators, people in this ticket, or the ticket "
            "opener can close tickets.",
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
