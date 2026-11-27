"""Where a tribe group's fleet post goes, and with which mention.

Every group fleet post (the daily roundup, the quiet pre-ping, the start
ping) goes to the group's channel (else its tribe's) and to each
corporation channel the group's managers approved
(docs/tribes/group-fleet-roundup.md):

| Post       | Group channel | Corporation channel |
|------------|---------------|---------------------|
| roundup    | silent        | silent              |
| pre_ping   | silent        | silent              |
| start_ping | group role    | @here               |
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from discord.outbox import on_commit_enqueue, queue_channel_message
from tribes.models import TribeGroupCorporationFollow

PostKind = Literal["roundup", "pre_ping", "start_ping"]

# Discord's SUPPRESS_NOTIFICATIONS flag: a silent message.
SILENT_MESSAGE_FLAG = 4096
SILENT_KINDS = ("roundup", "pre_ping")
CORPORATION_START_PING_CONTENT = "@here"


@dataclass(frozen=True)
class Destination:
    channel_id: int
    # None for the group's own channel.
    follow_id: int | None

    def apply(self, payload: dict, kind: PostKind) -> dict:
        """A copy of the payload with this destination's mention rule."""
        payload = dict(payload)
        if kind in SILENT_KINDS:
            payload["flags"] = SILENT_MESSAGE_FLAG
            payload["allowed_mentions"] = {"parse": []}
        elif self.follow_id is not None:
            # The group's role doesn't exist in a corporation's server.
            payload["content"] = CORPORATION_START_PING_CONTENT
            payload["allowed_mentions"] = {"parse": ["everyone"]}
        return payload


def forwarding_follows(group) -> list[TribeGroupCorporationFollow]:
    """The group's approved follows whose corporation bot is linked."""
    follows = TribeGroupCorporationFollow.objects.filter(
        tribe_group=group,
        status=TribeGroupCorporationFollow.STATUS_APPROVED,
    ).select_related("corporation")
    return [follow for follow in follows if follow.is_forwarding()]


def group_post_destinations(group, kind: PostKind) -> list[Destination]:
    """The group's channel first (when it has one), then each corporation
    channel that forwards the group's posts."""
    del kind  # Every kind goes to the same places; apply() differs.
    destinations = []
    channel_id = group.effective_discord_channel_id
    if channel_id:
        destinations.append(Destination(channel_id=channel_id, follow_id=None))
    destinations.extend(
        Destination(channel_id=follow.channel_id, follow_id=follow.id)
        for follow in forwarding_follows(group)
    )
    return destinations


def send_group_post(
    group, kind: PostKind, payload: dict, context: str, *, queue=None
) -> int:
    """Queue the post for every destination after commit; how many.

    ``queue`` posts to the group's own channel (``queue_channel_message``
    by default); callers pass theirs so the group's post goes out exactly
    as it did before forwarding existed.
    """
    queue = queue or queue_channel_message
    # pylint: disable-next=import-outside-toplevel
    from tribes.tasks import post_forwarded_fleet_message

    destinations = group_post_destinations(group, kind)
    for destination in destinations:
        body = destination.apply(payload, kind)
        if destination.follow_id is None:
            queue(destination.channel_id, payload=body, context=context)
        else:
            on_commit_enqueue(
                post_forwarded_fleet_message,
                (destination.follow_id, body, context),
                context=f"{context} (corporation follow {destination.follow_id})",
            )
    return len(destinations)
