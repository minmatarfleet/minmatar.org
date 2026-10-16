import json
from datetime import datetime
from pathlib import Path

from django.db import migrations

# 0008 deleted every Reddit post because none had a corporation yet. This
# puts the corporation posts back from the 2026-10-14 production backup, now
# owned by their corporation. The [FL33T] alliance post stays retired.
# Each post keeps its day, flair and Discord channel, goes out as a Discord
# reminder, and stays approved as it was before 0007. The last Reddit post is
# kept as history.
DATA = Path(__file__).parent / "data" / "0011_restored_corporation_posts.json"


def restore_channel(apps, row):
    """The post's Discord channel, registered if it isn't yet. All of them
    are text channels in the main alliance server."""
    DiscordGuild = apps.get_model("discord", "DiscordGuild")
    DiscordChannel = apps.get_model("discord", "DiscordChannel")
    channel = DiscordChannel.objects.filter(
        channel_id=row["discord_channel_id"]
    ).first()
    if channel is not None:
        return channel
    guild = DiscordGuild.objects.filter(
        guild_id=row["discord_guild_id"]
    ).first()
    if guild is None:
        print(
            f"\n  {row['corporation_name']}: Discord channel "
            f"#{row['discord_channel_name']} not restored (guild not synced)"
        )
        return None
    print(f"\n  Registering Discord channel #{row['discord_channel_name']}")
    return DiscordChannel.objects.create(
        channel_id=row["discord_channel_id"],
        guild=guild,
        name=row["discord_channel_name"],
        channel_type="text",
    )


def restore_posts(apps, schema_editor):
    EveCorporation = apps.get_model("eveonline", "EveCorporation")
    RedditPostTemplate = apps.get_model("reddit", "RedditPostTemplate")
    RedditPost = apps.get_model("reddit", "RedditPost")

    for row in json.loads(DATA.read_text(encoding="utf-8")):
        name = row["corporation_name"]
        corporation = EveCorporation.objects.filter(
            corporation_id=row["corporation_id"]
        ).first()
        if corporation is None:
            print(f"\n  Not restoring {name}'s Reddit post: no corporation")
            continue
        if RedditPostTemplate.objects.filter(corporation=corporation).exists():
            print(
                f"\n  Not restoring {name}'s Reddit post: CEO made a new one"
            )
            continue

        channel = None
        if row["discord_channel_id"]:
            channel = restore_channel(apps, row)

        template = RedditPostTemplate.objects.create(
            corporation=corporation,
            subreddit=row["subreddit"],
            title=row["title"],
            content=row["content"],
            posting_day=row["posting_day"],
            delivery_method="discord_reminder",
            approved=True,
            discord_channel=channel,
            flair_id=row["flair_id"],
        )
        if row["last_post_at"]:
            RedditPost.objects.create(
                template=template,
                status="posted",
                title=row["last_reddit_post_title"] or "",
                reddit_url=row["last_reddit_post_url"] or "",
                created_at=datetime.fromisoformat(row["last_post_at"]),
            )
        print(
            f"\n  Restored {name}'s Reddit post ({row['posting_day']}, "
            f"r/{row['subreddit']})"
        )


def remove_restored_posts(apps, schema_editor):
    RedditPostTemplate = apps.get_model("reddit", "RedditPostTemplate")
    titles = {
        row["title"] for row in json.loads(DATA.read_text(encoding="utf-8"))
    }
    RedditPostTemplate.objects.filter(title__in=titles).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0022_discordchannel_receive_buyback"),
        ("eveonline", "0106_merge_fw_payout_corporation_profile"),
        ("reddit", "0010_drop_last_fields"),
    ]

    operations = [
        migrations.RunPython(restore_posts, remove_restored_posts),
    ]
