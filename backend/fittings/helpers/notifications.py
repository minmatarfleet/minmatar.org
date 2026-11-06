"""Discord notifications for doctrine/fitting change requests."""

import logging

from app.links import site_url
from discord.client import DiscordClient
from discord.models import DiscordUser

logger = logging.getLogger(__name__)


def _discord_user_id_for_user(user) -> str | None:
    discord_user = DiscordUser.objects.filter(user_id=user.id).first()
    if discord_user:
        return str(discord_user.id)
    return None


def _send_dm(user, message: str):
    discord_id = _discord_user_id_for_user(user)
    if not discord_id:
        logger.info(
            "Skipping doctrine/fitting change DM for %s (no Discord link)",
            user,
        )
        return
    try:
        DiscordClient().send_dm(discord_id, message=message)
    except Exception:
        logger.warning(
            "Failed to send doctrine/fitting change DM to %s",
            user,
            exc_info=True,
        )


def build_daily_reminder_message(
    user, doctrine_count: int, fitting_count: int
) -> str:
    parts = ["**Doctrine/fitting changes awaiting your review**"]
    if doctrine_count:
        parts.append(f"- Doctrines: {doctrine_count}")
    if fitting_count:
        parts.append(f"- Fittings: {fitting_count}")
    parts.append(f"\nReview queue: {site_url('/ships/doctrines/review/')}")
    return "\n".join(parts)
