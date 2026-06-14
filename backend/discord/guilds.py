import logging

from django.conf import settings
from django.utils import timezone

from discord.client import DiscordClient
from discord.models import DiscordGuild

logger = logging.getLogger(__name__)
discord = DiscordClient()


def sync_discord_guilds(source_guilds=None):
    """
    Upsert DiscordGuild rows from the Discord API or an explicit guild list.

    When source_guilds is omitted, fetches guild membership via the bot token.
    Guilds missing from the latest sync are marked inactive rather than deleted.
    """
    if source_guilds is None:
        source_guilds = discord.get_bot_guilds()

    now = timezone.now()
    seen_ids = []
    for guild in source_guilds:
        guild_id = int(guild["id"])
        seen_ids.append(guild_id)
        DiscordGuild.objects.update_or_create(
            guild_id=guild_id,
            defaults={
                "name": guild["name"],
                "last_seen_at": now,
                "is_active": True,
            },
        )

    DiscordGuild.objects.exclude(guild_id__in=seen_ids).update(is_active=False)

    primary_id = settings.DISCORD_GUILD_ID
    DiscordGuild.objects.filter(guild_id=primary_id).update(is_primary=True)
    DiscordGuild.objects.exclude(guild_id=primary_id).update(is_primary=False)

    return len(seen_ids)
