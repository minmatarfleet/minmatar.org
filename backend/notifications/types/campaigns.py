"""Campaign notification type definitions and renderers."""

from __future__ import annotations

from notifications.discord_format import feature_color
from notifications.models import NotificationChannel
from notifications.registry import NotificationType, register

CAMPAIGN_COORDINATOR_INVITED_KEY = "campaigns.coordinator_invited"


def render_coordinator_invited(ctx: dict) -> dict:
    campaign = ctx["campaign_name"]
    character = ctx["character_name"]
    inviter = ctx.get("inviter") or "Minmatar Fleet"
    url = ctx.get("url") or ""
    title = f"You’re a coordinator for {campaign}"
    body = (
        f"{inviter} invited {character} to help coordinate {campaign}. "
        "Open the campaign page to see the plan, and add our bot to your "
        "Discord server to get its timers and fleet pings there."
    )
    description = (
        f"**{inviter}** invited **{character}** to help coordinate "
        f"**{campaign}**.\nOpen the campaign page to see the plan, and add "
        "our bot to your Discord server to get its timers and fleet pings "
        "there."
    )
    embed = {
        "author": {"name": "Campaigns"},
        "color": feature_color("campaigns"),
        "title": title,
        "description": description,
    }
    components = []
    if url:
        embed["url"] = url
        components = [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 5,
                        "label": "Open the campaign",
                        "url": url,
                    }
                ],
            }
        ]
    return {
        "title": title,
        "body": body,
        "url": url,
        "discord_message": description,
        "discord_embed": embed,
        "discord_components": components,
    }


CAMPAIGN_COORDINATOR_INVITED = register(
    NotificationType(
        key=CAMPAIGN_COORDINATOR_INVITED_KEY,
        feature="campaigns",
        label="Invited to coordinate a campaign",
        description="Tell me when I'm invited to help run a campaign.",
        channels=(NotificationChannel.DISCORD, NotificationChannel.WEB),
        defaults={
            NotificationChannel.DISCORD: True,
            NotificationChannel.WEB: True,
        },
        render=render_coordinator_invited,
        supports_topic_subscription=False,
    )
)
