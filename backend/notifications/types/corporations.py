"""Corporation notification type definitions and renderers."""

from __future__ import annotations

from app.links import site_url
from notifications.models import NotificationChannel
from notifications.registry import NotificationType, register

DISCORD_MEMBERS_KEY = "corporations.discord_members"

# Keep Discord embeds / Eve mail / web push under size limits.
_MAX_PEOPLE = 15


def corporation_settings_url(corporation) -> str:
    # pylint: disable-next=import-outside-toplevel
    from eveonline.helpers.corporations.slugs import corporation_slug

    slug = corporation_slug(corporation.name)
    return site_url(f"/alliance/corporations/{slug}/#settings")


def _person_line(person: dict) -> str:
    name = person.get("name") or person.get("username") or "Someone"
    username = person.get("username") or ""
    handle = f" (@{username})" if username and username != name else ""
    return f"- {name}{handle}: {person.get('reason') or 'Not allowed'}"


def render_discord_members(ctx: dict) -> dict:
    """People on a corp server the member policy doesn't allow."""
    people = ctx.get("people") or []
    server = ctx.get("server") or "your Discord"
    count = len(people)
    noun = "person" if count == 1 else "people"
    title = f"{count} {noun} to remove from {server}"
    lines = [_person_line(person) for person in people[:_MAX_PEOPLE]]
    if count > _MAX_PEOPLE:
        lines.append(f"And {count - _MAX_PEOPLE} more.")
    advice = (
        "Remove them in Discord, or allow them from the Discord settings on "
        "the site."
    )
    return {
        "title": title,
        "body": (
            f"{count} {noun} on {server} aren’t allowed by "
            f"{ctx.get('corporation') or 'your corporation'}’s Discord "
            "settings."
        ),
        "url": ctx.get("url") or "",
        "discord_message": "\n".join(lines + ["", advice]),
    }


DISCORD_MEMBERS = register(
    NotificationType(
        key=DISCORD_MEMBERS_KEY,
        feature="corporations",
        label="People to remove from my corporation’s Discord",
        description=(
            "When the corporation's Discord is set to tell the CEO, list "
            "people on the server who aren't allowed there."
        ),
        channels=(
            NotificationChannel.DISCORD,
            NotificationChannel.WEB,
        ),
        defaults={
            NotificationChannel.DISCORD: True,
            NotificationChannel.WEB: True,
        },
        render=render_discord_members,
        supports_topic_subscription=False,
    )
)
