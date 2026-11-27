"""A corporation's follows of tribe groups' fleet posts, seen from its
Settings tab: which channel, whether a chief approved it, and what the bot
lacks in that channel (docs/tribes/group-fleet-roundup.md)."""

from __future__ import annotations

import logging

from discord.client import DiscordClient
from eveonline.helpers.corporations.discord_bot import (
    EMBED_LINKS,
    INVITE_CHANNEL_TYPES,
    MENTION_EVERYONE,
    SEND_MESSAGES,
    VIEW_CHANNEL,
    is_connected,
)
from eveonline.models import EveCorporation

logger = logging.getLogger(__name__)

__all__ = [
    "EMBED_LINKS",
    "MENTION_EVERYONE",
    "SEND_MESSAGES",
    "FollowError",
    "bot_ready",
    "channel_permissions",
    "fleet_follows_response",
    "follow_warnings",
    "remove_follow",
    "save_follow",
]

ADMINISTRATOR = 1 << 3
ALL_PERMISSIONS = (1 << 53) - 1
# Only Alliance and Associate corporations can follow a group.
ELIGIBLE_TYPES = ("alliance", "associate")
MEMBER_OVERWRITE = 1


class FollowError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def bot_ready(corporation: EveCorporation) -> bool:
    return (
        is_connected(corporation)
        and corporation.discord_bot_status == EveCorporation.DISCORD_BOT_OK
    )


def channel_permissions(
    *,
    guild_id: int,
    user_id: int,
    roles: list[dict],
    member_role_ids: list,
    overwrites: list[dict],
) -> int:
    """A member's permissions in a channel, the way Discord computes them:
    @everyone and the member's roles, then the channel's @everyone, role
    and member overwrites. Administrator means everything."""
    by_id = {int(role["id"]): int(role["permissions"]) for role in roles}
    member_roles = {int(role_id) for role_id in member_role_ids}
    perms = by_id.get(guild_id, 0)
    for role_id in member_roles:
        perms |= by_id.get(role_id, 0)
    if perms & ADMINISTRATOR:
        return ALL_PERMISSIONS
    by_target = {int(o["id"]): o for o in overwrites}

    def apply(allow: int, deny: int) -> None:
        nonlocal perms
        perms = (perms & ~deny) | allow

    everyone = by_target.get(guild_id)
    if everyone:
        apply(int(everyone["allow"]), int(everyone["deny"]))
    allow = deny = 0
    for role_id in member_roles:
        overwrite = by_target.get(role_id)
        if overwrite and overwrite.get("type") != MEMBER_OVERWRITE:
            allow |= int(overwrite["allow"])
            deny |= int(overwrite["deny"])
    apply(allow, deny)
    member = by_target.get(user_id)
    if member and member.get("type") == MEMBER_OVERWRITE:
        apply(int(member["allow"]), int(member["deny"]))
    return perms


def follow_warnings(perms: int | None) -> list[str]:
    """What the bot lacks for fleet posts; [] when unknown or all there."""
    if perms is None or perms & ADMINISTRATOR:
        return []
    if not perms & VIEW_CHANNEL or not perms & SEND_MESSAGES:
        return ["cant_post"]
    warnings = []
    if not perms & EMBED_LINKS:
        warnings.append("no_embeds")
    if not perms & MENTION_EVERYONE:
        warnings.append("no_here")
    return warnings


class _GuildView:
    """The bot's view of the corporation's server, fetched once."""

    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.channels: dict[int, dict] = {}
        self._perms = None
        try:
            client = DiscordClient(guild_id=guild_id)
            raw = client.get_guild_channels_raw(guild_id)
            self.channels = {
                int(c["id"]): c
                for c in raw
                if c.get("type") in INVITE_CHANNEL_TYPES
            }
            bot_id = int(client.get_current_user()["id"])
            member = client.get_guild_member_raw(guild_id, bot_id)
            roles = client.get_roles()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning(
                "Could not read Discord server %s for fleet follows",
                guild_id,
                exc_info=True,
            )
            self.reachable = False
            return
        self.reachable = True
        self._perms = (bot_id, member.get("roles", []), roles)

    def permissions(self, channel_id: int) -> int | None:
        channel = self.channels.get(channel_id)
        if self._perms is None or channel is None:
            return None
        bot_id, member_role_ids, roles = self._perms
        return channel_permissions(
            guild_id=self.guild_id,
            user_id=bot_id,
            roles=roles,
            member_role_ids=member_role_ids,
            overwrites=channel.get("permission_overwrites") or [],
        )


def _followable_groups():
    # pylint: disable-next=import-outside-toplevel
    from tribes.models import TribeGroup

    return (
        TribeGroup.objects.filter(
            is_active=True, tribe__is_active=True, fleets_enabled=True
        )
        .select_related("tribe")
        .order_by("tribe__name", "name")
    )


def fleet_follows_response(
    corporation: EveCorporation, view: _GuildView | None = None
) -> dict:
    """The Settings tab's Fleet pings section."""
    # pylint: disable-next=import-outside-toplevel
    from tribes.models import TribeGroupCorporationFollow

    ready = bot_ready(corporation)
    if ready and view is None:
        view = _GuildView(corporation.discord_guild.guild_id)
    channels = view.channels.values() if ready and view else []
    follows = TribeGroupCorporationFollow.objects.filter(
        corporation=corporation
    ).select_related("tribe_group__tribe")
    return {
        "bot_ready": ready,
        "channels": [
            {"id": str(c["id"]), "name": c.get("name", "")}
            for c in sorted(
                channels, key=lambda c: (c.get("position", 0), int(c["id"]))
            )
        ],
        "followable_groups": [
            {
                "tribe_group_id": group.id,
                "name": group.name,
                "tribe_name": group.tribe.name,
            }
            for group in _followable_groups()
        ],
        "follows": [
            {
                "tribe_group_id": follow.tribe_group_id,
                "group_name": follow.tribe_group.name,
                "tribe_name": follow.tribe_group.tribe.name,
                "channel_id": str(follow.channel_id),
                "channel_name": follow.channel_name,
                "status": follow.status,
                "warnings": (
                    follow_warnings(view.permissions(follow.channel_id))
                    if ready and view
                    else []
                ),
                "last_delivery_ok": follow.last_delivery_ok,
                "last_delivery_error": follow.last_delivery_error,
                "last_delivery_at": follow.last_delivery_at,
            }
            for follow in follows
        ],
    }


def _check_can_follow(corporation: EveCorporation) -> None:
    if corporation.type not in ELIGIBLE_TYPES:
        raise FollowError("not_eligible")
    if not bot_ready(corporation):
        raise FollowError("not_connected")


def save_follow(
    corporation: EveCorporation, tribe_group_id: int, channel_id: str, user
) -> dict:
    """Ask to follow the group in this channel. A new follow, or a new
    channel, waits for a group chief's approval again."""
    # pylint: disable-next=import-outside-toplevel
    from tribes.models import TribeGroupCorporationFollow

    _check_can_follow(corporation)
    group = _followable_groups().filter(pk=tribe_group_id).first()
    if group is None:
        raise FollowError("unknown_group", status=404)
    view = _GuildView(corporation.discord_guild.guild_id)
    if not view.reachable:
        raise FollowError("discord_unreachable")
    try:
        channel = view.channels.get(int(channel_id))
    except ValueError:
        channel = None
    if channel is None:
        raise FollowError("unknown_channel")
    follow = TribeGroupCorporationFollow.objects.filter(
        tribe_group=group, corporation=corporation
    ).first()
    if follow is None:
        follow = TribeGroupCorporationFollow(
            tribe_group=group, corporation=corporation, requested_by=user
        )
    if follow.pk is None or follow.channel_id != int(channel["id"]):
        follow.channel_id = int(channel["id"])
        follow.status = TribeGroupCorporationFollow.STATUS_REQUESTED
        follow.requested_by = user
        follow.decided_by = None
        follow.decided_at = None
    follow.channel_name = channel.get("name", "")[:100]
    follow.save()
    return fleet_follows_response(corporation, view)


def remove_follow(corporation: EveCorporation, tribe_group_id: int) -> dict:
    """Stop following the group: nothing more is forwarded."""
    # pylint: disable-next=import-outside-toplevel
    from tribes.models import TribeGroupCorporationFollow

    TribeGroupCorporationFollow.objects.filter(
        corporation=corporation, tribe_group_id=tribe_group_id
    ).delete()
    return fleet_follows_response(corporation)
