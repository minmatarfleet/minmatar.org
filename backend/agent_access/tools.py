"""The Discord tools an agent may call, and the rules around them.

Reads reach every server the bot is in, except what `AgentDiscordReadBlock`
excludes. Writes are two: send a message and add a reaction. They need a
key that may write, writes switched on, the per-key rate limits, and an
`AgentDiscordPostTarget` for the channel. Messages never ping @everyone,
@here or roles. There are no tools for moderation, roles, permissions,
webhooks, invites, edits or deletes, so the bot's other rights (including
Administrator on some servers) are out of reach.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

from django.utils import timezone

from . import discord_api
from .discord_api import AgentDiscordError, snowflake
from .models import (
    AgentDiscordCall,
    AgentDiscordPostTarget,
    AgentDiscordReadBlock,
    AgentDiscordSettings,
    AgentKey,
)

ADMINISTRATOR = 0x8
THREAD_TYPES = {10, 11, 12}
MAX_MESSAGE_LENGTH = 2000
MAX_MENTIONS = 10


class ToolRefused(Exception):
    """The agent asked for something it may not do."""


@dataclass
class Context:
    key: AgentKey
    settings: AgentDiscordSettings
    guild_id: str = ""
    channel_id: str = ""
    _channels: dict = field(default_factory=dict)
    _targets: dict = field(default_factory=dict)

    def post_targets(self, guild_id: str) -> list:
        if guild_id not in self._targets:
            self._targets[guild_id] = list(
                AgentDiscordPostTarget.objects.filter(guild_id=guild_id)
            )
        return self._targets[guild_id]

    def channel(self, channel_id: str) -> dict:
        if channel_id not in self._channels:
            self._channels[channel_id] = discord_api.get(
                f"/channels/{channel_id}"
            )
        return self._channels[channel_id]


@dataclass
class Tool:
    name: str
    description: str
    properties: dict
    required: list
    handler: Callable
    is_write: bool = False

    def definition(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.properties,
                "required": self.required,
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": not self.is_write,
                "destructiveHint": False,
                "openWorldHint": True,
            },
        }


# --- access checks -------------------------------------------------------


def _blocked(guild_id: str, *channel_ids: str) -> bool:
    ids = [c for c in channel_ids if c]
    return (
        AgentDiscordReadBlock.objects.filter(guild_id=guild_id)
        .filter(channel_id__in=["", *ids])
        .exists()
    )


def check_guild(ctx: Context, guild_id) -> str:
    guild_id = snowflake(guild_id, "guild_id")
    if _blocked(guild_id):
        raise ToolRefused("This server is blocked for agents")
    ctx.guild_id = guild_id
    return guild_id


def _lineage(ctx: Context, channel: dict) -> list[str]:
    """The channel, its parent, and for a thread the parent's category."""
    ids = [channel["id"], channel.get("parent_id") or ""]
    if channel.get("type") in THREAD_TYPES and channel.get("parent_id"):
        parent = ctx.channel(channel["parent_id"])
        ids.append(parent.get("parent_id") or "")
    return [i for i in ids if i]


def check_channel(ctx: Context, channel_id) -> dict:
    """The channel, when it is in a server and not blocked."""
    channel_id = snowflake(channel_id, "channel_id")
    channel = ctx.channel(channel_id)
    guild_id = channel.get("guild_id")
    if not guild_id:
        raise ToolRefused("Only server channels are available, not DMs")
    ctx.guild_id = guild_id
    ctx.channel_id = channel_id
    if _blocked(guild_id, *_lineage(ctx, channel)):
        raise ToolRefused("This channel is blocked for agents")
    return channel


def can_post(ctx: Context, channel: dict) -> bool:
    for target in ctx.post_targets(channel.get("guild_id") or ""):
        if not target.channel_id or target.channel_id == channel["id"]:
            return True
        if (
            target.include_threads
            and channel.get("type") in THREAD_TYPES
            and target.channel_id == channel.get("parent_id")
        ):
            return True
    return False


def check_write(ctx: Context, channel: dict) -> None:
    if not ctx.key.can_write:
        raise ToolRefused("This key is read-only")
    if not ctx.settings.writes_enabled:
        raise ToolRefused("Agent writes are switched off")
    if not can_post(ctx, channel):
        raise ToolRefused(
            "Posting here is not allowed. A Discord admin can add it under "
            "Agent access > post targets."
        )
    now = timezone.now()
    writes = AgentDiscordCall.objects.filter(
        key=ctx.key, is_write=True, ok=True
    )
    if (
        writes.filter(created_at__gte=now - timedelta(minutes=1)).count()
        >= ctx.settings.writes_per_minute
    ):
        raise ToolRefused("Write rate limit (per minute); wait and retry")
    if (
        writes.filter(created_at__gte=now - timedelta(days=1)).count()
        >= ctx.settings.writes_per_day
    ):
        raise ToolRefused("Daily write limit reached for this key")


# --- shaping responses -----------------------------------------------------


def _limit(args: dict, default: int, maximum: int) -> int:
    try:
        value = int(args.get("limit", default))
    except (TypeError, ValueError) as e:
        raise ToolRefused("limit must be a number") from e
    return max(1, min(value, maximum))


def _user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "display_name": user.get("global_name"),
        "bot": bool(user.get("bot")),
    }


def _channel(channel: dict, ctx: Context) -> dict:
    out = {
        "id": channel.get("id"),
        "guild_id": channel.get("guild_id"),
        "name": channel.get("name"),
        "type": channel.get("type"),
        "parent_id": channel.get("parent_id"),
        "topic": channel.get("topic"),
        "can_post": can_post(ctx, channel),
    }
    meta = channel.get("thread_metadata")
    if meta:
        out["archived"] = meta.get("archived")
        out["locked"] = meta.get("locked")
        out["message_count"] = channel.get("message_count")
    return out


def _attachments(message: dict) -> list:
    return [
        {
            "id": a.get("id"),
            "filename": a.get("filename"),
            "content_type": a.get("content_type"),
            "size": a.get("size"),
            "url": a.get("url"),
        }
        for a in message.get("attachments") or []
    ]


def _message(message: dict) -> dict:
    reference = message.get("message_reference") or {}
    return {
        "id": message.get("id"),
        "channel_id": message.get("channel_id"),
        "author": _user(message.get("author")),
        "content": message.get("content"),
        "timestamp": message.get("timestamp"),
        "edited_timestamp": message.get("edited_timestamp"),
        "reply_to": reference.get("message_id"),
        "thread_id": (message.get("thread") or {}).get("id"),
        "mention_ids": [u.get("id") for u in message.get("mentions") or []],
        "attachments": _attachments(message),
        "embeds": [
            {
                "title": e.get("title"),
                "description": (e.get("description") or "")[:1000],
                "url": e.get("url"),
            }
            for e in message.get("embeds") or []
        ],
        "reactions": [
            {
                "emoji": (r.get("emoji") or {}).get("name"),
                "count": r.get("count"),
            }
            for r in message.get("reactions") or []
        ],
    }


def _member(member: dict) -> dict:
    return {
        "user": _user(member.get("user")),
        "nick": member.get("nick"),
        "role_ids": member.get("roles") or [],
        "joined_at": member.get("joined_at"),
    }


def _visible_threads(ctx: Context, guild_id: str, threads: list) -> list:
    blocks = set(
        AgentDiscordReadBlock.objects.filter(guild_id=guild_id).values_list(
            "channel_id", flat=True
        )
    )
    return [
        _channel(t, ctx)
        for t in threads
        if t.get("id") not in blocks and t.get("parent_id") not in blocks
    ]


# --- read tools --------------------------------------------------------------


def list_servers(ctx: Context, args: dict) -> dict:
    guilds = discord_api.get("/users/@me/guilds", {"limit": 200}) or []
    blocked = set(
        AgentDiscordReadBlock.objects.filter(channel_id="").values_list(
            "guild_id", flat=True
        )
    )
    postable = set(
        AgentDiscordPostTarget.objects.values_list("guild_id", flat=True)
    )
    return {
        "servers": [
            {
                "id": g["id"],
                "name": g.get("name"),
                "bot_is_admin": bool(
                    int(g.get("permissions") or 0) & ADMINISTRATOR
                ),
                "has_post_targets": g["id"] in postable,
            }
            for g in guilds
            if g["id"] not in blocked
        ]
    }


def list_channels(ctx: Context, args: dict) -> dict:
    guild_id = check_guild(ctx, args.get("guild_id"))
    channels = discord_api.get(f"/guilds/{guild_id}/channels") or []
    blocks = set(
        AgentDiscordReadBlock.objects.filter(guild_id=guild_id).values_list(
            "channel_id", flat=True
        )
    )
    visible = []
    for channel in channels:
        channel.setdefault("guild_id", guild_id)
        if channel["id"] in blocks or channel.get("parent_id") in blocks:
            continue
        visible.append(_channel(channel, ctx))
    return {"channels": visible}


def get_channel_info(ctx: Context, args: dict) -> dict:
    return _channel(check_channel(ctx, args.get("channel_id")), ctx)


def list_active_threads(ctx: Context, args: dict) -> dict:
    guild_id = check_guild(ctx, args.get("guild_id"))
    data = discord_api.get(f"/guilds/{guild_id}/threads/active") or {}
    return {
        "threads": _visible_threads(ctx, guild_id, data.get("threads", []))
    }


def list_archived_threads(ctx: Context, args: dict) -> dict:
    channel = check_channel(ctx, args.get("channel_id"))
    kind = "private" if args.get("private") else "public"
    params = {"limit": _limit(args, 25, 50)}
    if args.get("before"):
        params["before"] = str(args["before"])
    data = (
        discord_api.get(
            f"/channels/{channel['id']}/threads/archived/{kind}", params
        )
        or {}
    )
    return {
        "threads": _visible_threads(
            ctx, channel["guild_id"], data.get("threads", [])
        ),
        "has_more": bool(data.get("has_more")),
    }


def read_messages(ctx: Context, args: dict) -> dict:
    channel = check_channel(ctx, args.get("channel_id"))
    params = {"limit": _limit(args, 50, 100)}
    anchors = [a for a in ("before", "after", "around") if args.get(a)]
    if len(anchors) > 1:
        raise ToolRefused("Use only one of before, after, around")
    for anchor in anchors:
        params[anchor] = snowflake(args[anchor], anchor)
    messages = (
        discord_api.get(f"/channels/{channel['id']}/messages", params) or []
    )
    return {"messages": [_message(m) for m in messages]}


def get_message(ctx: Context, args: dict) -> dict:
    channel = check_channel(ctx, args.get("channel_id"))
    message_id = snowflake(args.get("message_id"), "message_id")
    return _message(
        discord_api.get(f"/channels/{channel['id']}/messages/{message_id}")
    )


def get_attachment(ctx: Context, args: dict) -> dict:
    message = get_message(ctx, args)
    return {"message_id": message["id"], "attachments": message["attachments"]}


def search_members(ctx: Context, args: dict) -> dict:
    guild_id = check_guild(ctx, args.get("guild_id"))
    query = str(args.get("query") or "").strip()
    if not query:
        raise ToolRefused("query is required")
    members = discord_api.get(
        f"/guilds/{guild_id}/members/search",
        {"query": query[:100], "limit": _limit(args, 10, 25)},
    )
    return {"members": [_member(m) for m in members or []]}


def get_member(ctx: Context, args: dict) -> dict:
    guild_id = check_guild(ctx, args.get("guild_id"))
    user_id = snowflake(args.get("user_id"), "user_id")
    return _member(discord_api.get(f"/guilds/{guild_id}/members/{user_id}"))


def list_roles(ctx: Context, args: dict) -> dict:
    guild_id = check_guild(ctx, args.get("guild_id"))
    roles = discord_api.get(f"/guilds/{guild_id}/roles") or []
    return {
        "roles": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "position": r.get("position"),
                "is_admin": bool(
                    int(r.get("permissions") or 0) & ADMINISTRATOR
                ),
                "managed": bool(r.get("managed")),
            }
            for r in roles
        ]
    }


# --- write tools -----------------------------------------------------------


def send_message(ctx: Context, args: dict) -> dict:
    channel = check_channel(ctx, args.get("channel_id"))
    content = str(args.get("content") or "")
    if not content.strip():
        raise ToolRefused("content is required")
    if len(content) > MAX_MESSAGE_LENGTH:
        raise ToolRefused(f"content is over {MAX_MESSAGE_LENGTH} characters")
    mention_ids = [
        snowflake(u, "mention_user_ids")
        for u in (args.get("mention_user_ids") or [])
    ]
    if len(mention_ids) > MAX_MENTIONS:
        raise ToolRefused(f"At most {MAX_MENTIONS} users can be mentioned")
    check_write(ctx, channel)
    payload = {
        "content": content,
        # Never @everyone, @here or roles; only the users named here ping.
        "allowed_mentions": {
            "parse": [],
            "users": mention_ids,
            "replied_user": False,
        },
    }
    if args.get("reply_to_message_id"):
        payload["message_reference"] = {
            "message_id": snowflake(
                args["reply_to_message_id"], "reply_to_message_id"
            ),
            "fail_if_not_exists": False,
        }
    message = discord_api.post_message(channel["id"], payload)
    return {
        "id": message.get("id"),
        "channel_id": message.get("channel_id"),
        "url": (
            "https://discord.com/channels/"
            f"{channel['guild_id']}/{channel['id']}/{message.get('id')}"
        ),
    }


def add_reaction(ctx: Context, args: dict) -> dict:
    channel = check_channel(ctx, args.get("channel_id"))
    message_id = snowflake(args.get("message_id"), "message_id")
    emoji = str(args.get("emoji") or "").strip()
    if not emoji or len(emoji) > 64:
        raise ToolRefused("emoji must be a unicode emoji or name:id")
    check_write(ctx, channel)
    discord_api.put_reaction(channel["id"], message_id, emoji)
    return {"ok": True}


# --- registry ----------------------------------------------------------------

_ID = {"type": "string", "description": "A Discord id (snowflake)."}
_LIMIT = {"type": "integer", "minimum": 1}

TOOLS = [
    Tool(
        "list_servers",
        "List the Discord servers the bot is in, with whether the bot is an "
        "administrator there and whether any channel allows agent posts.",
        {},
        [],
        list_servers,
    ),
    Tool(
        "list_channels",
        "List a server's channels and categories (not threads).",
        {"guild_id": _ID},
        ["guild_id"],
        list_channels,
    ),
    Tool(
        "get_channel_info",
        "Details of one channel or thread, including its server, parent, "
        "whether it is archived, and whether the agent may post there.",
        {"channel_id": _ID},
        ["channel_id"],
        get_channel_info,
    ),
    Tool(
        "list_active_threads",
        "List a server's active (unarchived) threads.",
        {"guild_id": _ID},
        ["guild_id"],
        list_active_threads,
    ),
    Tool(
        "list_archived_threads",
        "List archived threads under a channel, newest first.",
        {
            "channel_id": _ID,
            "private": {
                "type": "boolean",
                "description": "Private threads instead of public ones.",
            },
            "limit": {**_LIMIT, "maximum": 50},
            "before": {
                "type": "string",
                "description": "ISO timestamp: threads archived before it.",
            },
        },
        ["channel_id"],
        list_archived_threads,
    ),
    Tool(
        "read_messages",
        "Read messages in a channel or thread, newest first (up to 100). "
        "Page with before/after/around a message id.",
        {
            "channel_id": _ID,
            "limit": {**_LIMIT, "maximum": 100},
            "before": _ID,
            "after": _ID,
            "around": _ID,
        },
        ["channel_id"],
        read_messages,
    ),
    Tool(
        "get_message",
        "Read one message.",
        {"channel_id": _ID, "message_id": _ID},
        ["channel_id", "message_id"],
        get_message,
    ),
    Tool(
        "get_attachment",
        "A message's attachments with fresh download URLs (screenshots, "
        "logs). Discord's URLs expire, so fetch them right away.",
        {"channel_id": _ID, "message_id": _ID},
        ["channel_id", "message_id"],
        get_attachment,
    ),
    Tool(
        "search_members",
        "Find server members whose username or nickname starts with query.",
        {
            "guild_id": _ID,
            "query": {"type": "string"},
            "limit": {**_LIMIT, "maximum": 25},
        },
        ["guild_id", "query"],
        search_members,
    ),
    Tool(
        "get_member",
        "One server member: nickname, role ids, join date.",
        {"guild_id": _ID, "user_id": _ID},
        ["guild_id", "user_id"],
        get_member,
    ),
    Tool(
        "list_roles",
        "List a server's roles.",
        {"guild_id": _ID},
        ["guild_id"],
        list_roles,
    ),
    Tool(
        "send_message",
        "Post a message as the bot, in a channel or thread that allows "
        "agent posts (see get_channel_info's can_post). It never pings "
        "@everyone, @here or roles; users ping only when listed in "
        "mention_user_ids. Plain text up to 2000 characters.",
        {
            "channel_id": _ID,
            "content": {"type": "string", "maxLength": MAX_MESSAGE_LENGTH},
            "reply_to_message_id": _ID,
            "mention_user_ids": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": MAX_MENTIONS,
            },
        },
        ["channel_id", "content"],
        send_message,
        is_write=True,
    ),
    Tool(
        "add_reaction",
        "React to a message as the bot, where agent posts are allowed.",
        {
            "channel_id": _ID,
            "message_id": _ID,
            "emoji": {
                "type": "string",
                "description": "A unicode emoji, or name:id for a custom one.",
            },
        },
        ["channel_id", "message_id", "emoji"],
        add_reaction,
        is_write=True,
    ),
]

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}

__all__ = ["AgentDiscordError", "Context", "TOOLS", "TOOLS_BY_NAME"]
