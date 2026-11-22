"""What the campaign bot posts to Discord, and where.

Four channels, each picked on the coordination server (``Campaign``) and on
every server a coordinator linked (``CampaignDiscordLink``):

| Slot | Posts | Ping |
| --- | --- | --- |
| intel | one line per new structure and per new timer | none |
| timers | one message with every upcoming timer, edited in place | none |
| schedule | one message with every fleet form-up, edited in place | none |
| fleets | one message when a campaign fleet starts forming | @everyone |

A linked server only gets what its coordinators may see
(``Campaign.coordinator_scopes``): structures for structure intel, timers
for timer intel and the timerboard, fleets for the schedule and the pings.

Single posts go through ``discord.outbox`` after the transaction commits.
The two boards are refreshed by ``campaigns.tasks.refresh_campaign_boards``,
which edits the stored message and only posts a new one when the old one is
gone.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

from django.db.models import Q
from django.utils import timezone
from requests import HTTPError

from app.links import new_player_fleet_guide_url, site_url
from campaigns.constants import STRUCTURE_TYPE_IDS
from campaigns.models import (
    Campaign,
    CampaignDiscordBoard,
    CampaignStatus,
    CampaignStructure,
    StructureAffiliation,
)
from campaigns.services import disclosure
from campaigns.services.structures import structure_affiliation
from campaigns.services.tickers import alliance_tickers, owner_alliance
from campaigns.services.timers import TYPE_NAMES, timer_stage

logger = logging.getLogger(__name__)

INTEL = "intel"
TIMERS = "timers"
SCHEDULE = "schedule"
FLEETS = "fleets"
SLOTS = (INTEL, TIMERS, SCHEDULE, FLEETS)

# Campaign statuses the bot posts for: planning and running, not finished.
POSTING_STATUSES = (
    CampaignStatus.DRAFT,
    CampaignStatus.SCHEDULED,
    CampaignStatus.ACTIVE,
    CampaignStatus.PAUSED,
)

DISCORD_MESSAGE_LIMIT = 2000
NO_MENTIONS = {"parse": []}
EVERYONE = {"parse": ["everyone"]}

STATE_LABELS = {
    "anchoring": "Anchoring",
    "unanchoring": "Unanchoring",
    "armor": "Armor",
    "hull": "Hull",
}
SIDE_HEADINGS = (
    (StructureAffiliation.HOSTILE, "Enemy timers"),
    (StructureAffiliation.FRIENDLY, "Friendly timers"),
    (StructureAffiliation.NEUTRAL, "Other timers"),
)


@dataclass(frozen=True)
class Destination:
    channel_id: int
    # A coordinator's server: the fleet ping links to the campaign page,
    # not to a fleet page only alliance members can open.
    relay: bool


def _slot_scope(slot: str, topic: str = "") -> str:
    if slot == INTEL:
        return topic
    return TIMERS if slot == TIMERS else FLEETS


def destinations(
    campaign: Campaign, slot: str, topic: str = ""
) -> list[Destination]:
    """Channels picked for ``slot``. ``topic`` is the intel kind
    (``structures`` or ``timers``) and decides what a linked server gets."""
    if campaign.status not in POSTING_STATUSES:
        return []
    found = []
    ours = getattr(campaign, f"coordination_{slot}_channel_id")
    if ours:
        found.append(Destination(int(ours), relay=False))
    if disclosure.coordinator_may(campaign, _slot_scope(slot, topic)):
        seen = {ours}
        for link in campaign.discord_links.all():
            channel_id = getattr(link, f"{slot}_channel_id")
            if channel_id and channel_id not in seen:
                seen.add(channel_id)
                found.append(Destination(int(channel_id), relay=True))
    return found


def campaign_url(campaign: Campaign, tab: str = "") -> str:
    return site_url(
        f"/campaigns/{campaign.slug}/" + (f"#{tab}" if tab else "")
    )


def _when(at) -> str:
    stamp = int(at.timestamp())
    return f"{at.strftime('%Y-%m-%d %H:%M')} EVE (<t:{stamp}:R>)"


def _clip(lines: list[str], head: str, foot: str = "") -> str:
    """``head`` and as many lines as fit in one Discord message, then an
    "…and N more" line."""
    budget = DISCORD_MESSAGE_LIMIT - len(head) - len(foot) - 1
    shown = []
    used = 0
    for index, line in enumerate(lines):
        left = len(lines) - index - 1
        more = len(f"…and {left} more\n") if left else 0
        if used + len(line) + more > budget:
            shown.append(f"…and {len(lines) - index} more\n")
            break
        shown.append(line)
        used += len(line)
    return (head + "".join(shown) + foot).rstrip()


def _button(label: str, url: str) -> list[dict]:
    return [
        {
            "type": 1,
            "components": [
                {"type": 2, "style": 5, "label": label, "url": url}
            ],
        }
    ]


# --- Intel ---------------------------------------------------------------

IMAGE_SERVER = "https://images.evetech.net"
SIDE_WORDS = {
    StructureAffiliation.HOSTILE: "Enemy",
    StructureAffiliation.FRIENDLY: "Friendly",
    StructureAffiliation.NEUTRAL: "Neutral",
}
# Embed edge colour by side: fleet red, alliance blue, slate.
SIDE_COLORS = {
    StructureAffiliation.HOSTILE: 0xB91C1C,
    StructureAffiliation.FRIENDLY: 0x2B6CB0,
    StructureAffiliation.NEUTRAL: 0x4A5568,
}
FITTING_FIELD_LIMIT = 1000


def _owner(structure: CampaignStructure) -> str:
    alliance_id, alliance_name = owner_alliance(structure)
    if alliance_id:
        ticker = alliance_tickers([alliance_id], structure.campaign).get(
            alliance_id
        )
        if ticker:
            return f"[{ticker}]"
    return alliance_name or structure.corporation_name or "Unknown owner"


def _side(structure: CampaignStructure | None) -> str:
    if structure is None:
        return StructureAffiliation.NEUTRAL
    return structure_affiliation(structure)


def _type_id(structure_type: str, structure=None) -> int | None:
    if structure is not None and structure.type_id:
        return int(structure.type_id)
    return STRUCTURE_TYPE_IDS.get(structure_type)


def _named(name: str, ticker: str = "") -> str:
    return f"{name} [{ticker}]" if ticker and name else name or ticker


def _recorded_by(user) -> str:
    if user is None:
        return ""
    # pylint: disable-next=import-outside-toplevel
    from eveonline.helpers.characters.characters import (
        user_primary_character,
    )

    character = user_primary_character(user)
    return character.character_name if character else user.username


def _timer_text(timer) -> str:
    _, final = timer_stage(timer.type, timer.state)
    state = STATE_LABELS.get(timer.state, timer.state.title())
    stamp = int(timer.timer.timestamp())
    return (
        f"{state}{' (final)' if final else ''}\n"
        f"{timer.timer.strftime('%Y-%m-%d %H:%M')} EVE\n"
        f"<t:{stamp}:F> · <t:{stamp}:R>"
    )


def _intel_embed(
    campaign: Campaign,
    *,
    heading: str,
    structure: CampaignStructure | None,
    timer=None,
) -> dict:
    """One structure (and its timer) with everything we know about it."""
    structure_type = structure.structure_type if structure else timer.type
    type_name = TYPE_NAMES.get(structure_type, structure_type)
    name = structure.name if structure else timer.name
    system = structure.system_name if structure else timer.system_name
    side = _side(structure)

    fields = []

    def add(label: str, value, inline: bool = True) -> None:
        if value not in (None, ""):
            fields.append(
                {"name": label, "value": str(value)[:1024], "inline": inline}
            )

    if timer is not None:
        add("Timer", _timer_text(timer), inline=False)
    add("Side", SIDE_WORDS[side])
    add("System", system)
    add("Type", type_name)

    author = None
    if structure is not None:
        alliance_id, alliance_name = owner_alliance(structure)
        tickers = alliance_tickers(
            [alliance_id, structure.related_alliance_id], campaign
        )
        add("Corporation", structure.corporation_name)
        add(
            "Alliance",
            _named(
                structure.alliance_name, tickers.get(structure.alliance_id)
            ),
        )
        if structure.related_alliance_name:
            add(
                "Affiliated with",
                _named(
                    structure.related_alliance_name,
                    tickers.get(structure.related_alliance_id),
                ),
            )
        add("Status", structure.get_status_display())
        if structure.reinforce_hour is not None:
            add("Reinforce hour", f"{structure.reinforce_hour:02d}:00 EVE")
        add("Source", structure.get_source_display())
        add("Recorded by", _recorded_by(structure.created_by))
        if structure.fitting.strip():
            fitting = structure.fitting.strip()
            if len(fitting) > FITTING_FIELD_LIMIT:
                fitting = fitting[: FITTING_FIELD_LIMIT - 1] + "…"
            add("Fitting", f"```\n{fitting}\n```", inline=False)
        if alliance_id:
            ticker = tickers.get(alliance_id)
            author = {
                "name": _named(alliance_name, ticker),
                "icon_url": f"{IMAGE_SERVER}/alliances/{alliance_id}"
                "/logo?size=64",
            }
        elif structure.corporation_id:
            author = {
                "name": structure.corporation_name,
                "icon_url": f"{IMAGE_SERVER}/corporations/"
                f"{structure.corporation_id}/logo?size=64",
            }
    else:
        add("Alliance", timer.alliance_name)
        add("Corporation", timer.corporation_name)
        add("Recorded by", _recorded_by(timer.created_by))

    tab = "timers" if timer is not None else "structures"
    embed = {
        "title": f"{type_name} · {name}"[:256],
        "url": campaign_url(campaign, tab),
        "description": f"{heading} for **{campaign.name}**",
        "color": SIDE_COLORS[side],
        "fields": fields,
        "footer": {"text": campaign.name},
        "timestamp": timezone.now().isoformat(),
    }
    type_id = _type_id(structure_type, structure)
    if type_id:
        embed["thumbnail"] = {
            "url": f"{IMAGE_SERVER}/types/{type_id}/render?size=128"
        }
    if author:
        embed["author"] = author
    return embed


def structure_intel(structure: CampaignStructure) -> dict:
    campaign = structure.campaign
    return {
        "embeds": [
            _intel_embed(
                campaign, heading="New structure", structure=structure
            )
        ],
        "allowed_mentions": NO_MENTIONS,
        "components": _button(
            "Open structures", campaign_url(campaign, "structures")
        ),
    }


def timer_intel(campaign: Campaign, timer) -> dict:
    structure = (
        CampaignStructure.objects.filter(campaign=campaign, timer=timer)
        .order_by("-id")
        .first()
    )
    return {
        "embeds": [
            _intel_embed(
                campaign, heading="New timer", structure=structure, timer=timer
            )
        ],
        "allowed_mentions": NO_MENTIONS,
        "components": _button("Open timers", campaign_url(campaign, "timers")),
    }


# --- Timerboard ----------------------------------------------------------


def upcoming_timers(campaign: Campaign) -> list[tuple[object, object]]:
    """(timer, structure or None) for every timer still to come."""
    # Imported here: structures imports campaigns at load time.
    from structures.models import EveStructureTimer  # pylint: disable=C0415

    structures = {
        s.timer_id: s
        for s in campaign.structures.filter(timer__isnull=False)
        .select_related("campaign")
        .order_by("id")
    }
    timers = (
        EveStructureTimer.objects.filter(
            Q(campaign=campaign) | Q(id__in=list(structures))
        )
        .filter(timer__gt=timezone.now())
        .distinct()
        .order_by("timer")
    )
    return [(timer, structures.get(timer.id)) for timer in timers]


def timerboard(campaign: Campaign) -> dict:
    parties = list(campaign.parties.all())
    by_side: dict[str, list[str]] = {side: [] for side, _ in SIDE_HEADINGS}
    for timer, structure in upcoming_timers(campaign):
        side = (
            structure_affiliation(structure, parties)
            if structure
            else StructureAffiliation.NEUTRAL
        )
        _, final = timer_stage(timer.type, timer.state)
        state = STATE_LABELS.get(timer.state, timer.state.title())
        owner = _owner(structure) if structure else timer.alliance_name or ""
        line = (
            f"- {_when(timer.timer)} · {timer.system_name} · "
            f"{TYPE_NAMES.get(timer.type, timer.type)} "
            f"**{structure.name if structure else timer.name}** · "
            f"{state}{' (final)' if final else ''}"
            + (f" · {owner}" if owner else "")
            + "\n"
        )
        by_side[side].append(line)

    lines = []
    for side, heading in SIDE_HEADINGS:
        if by_side[side]:
            lines.append(f"### {heading}\n")
            lines.extend(by_side[side])
    head = f"## {campaign.name} · Timers\n"
    if not lines:
        lines = ["No upcoming timers.\n"]
    stamp = int(timezone.now().timestamp())
    return {
        "content": _clip(lines, head, f"-# Updated <t:{stamp}:R>"),
        "allowed_mentions": NO_MENTIONS,
        "components": _button("Open timers", campaign_url(campaign, "timers")),
    }


# --- Fleet schedule and pings --------------------------------------------


def scheduled_fleets(campaign: Campaign):
    """Campaign fleets still to form up, and the ones forming now.

    Private fleets never show, as on the alliance schedule; standing fleets
    and gangs form on the spot.
    """
    # Imported here: fleets imports campaigns at load time.
    # pylint: disable=import-outside-toplevel
    from fleets.models import CAMPAIGN_FLEET_TYPES, EveFleet

    now = timezone.now()
    return (
        EveFleet.objects.filter(campaign=campaign, invite_only=False)
        .exclude(type__in=CAMPAIGN_FLEET_TYPES)
        .exclude(status__in=("cancelled", "complete"))
        .filter(Q(start_time__gte=now) | Q(status="active"))
        .select_related("location", "doctrine", "audience")
        .order_by("start_time")
    )


NO_FLEETS_LINE = "- No upcoming fleets, go touch grass you nerd"


def _schedule_line(fleet) -> str:
    """A #schedule line: emoji, EVE time, local time, FC; then the
    objective, and whether it is forming now."""
    # pylint: disable-next=import-outside-toplevel
    from fleets.tasks import get_fleet_emoji

    fc = fleet.fleet_commander
    when = fleet.start_time.strftime("%Y-%m-%d %H:%M")
    emoji = get_fleet_emoji(fleet.type)
    line = (
        f"- {emoji + ' ' if emoji else ''}{when} EVE "
        f"(<t:{int(fleet.start_time.timestamp())}>)"
        + (f" {fc.character_name}" if fc else "")
    )
    if fleet.objective:
        line += f" · {fleet.objective}"
    if fleet.status == "active":
        line += " · **forming now**"
    return line + "\n"


def schedule(campaign: Campaign) -> dict:
    """The campaign's fleets in the alliance #schedule format, grouped by
    formup location."""
    by_location: dict[str, list[str]] = {}
    for fleet in scheduled_fleets(campaign):
        location = fleet.formup_location
        name = location.location_name if location else "No Location"
        by_location.setdefault(name, []).append(_schedule_line(fleet))
    lines = []
    for name in sorted(by_location):
        lines.append(f"\n**{name}**\n")
        lines.extend(by_location[name])
    if not lines:
        lines = [NO_FLEETS_LINE]
    return {
        "content": _clip(lines, f"## Fleet Schedule · {campaign.name}\n"),
        "allowed_mentions": NO_MENTIONS,
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 5,
                        "label": "View Fleet Board",
                        "url": campaign_url(campaign, "fleets"),
                    },
                    {
                        "type": 2,
                        "style": 5,
                        "label": "New Player Instructions",
                        "url": new_player_fleet_guide_url(),
                    },
                ],
            }
        ],
    }


def fleet_ping(fleet, relay: bool) -> dict:
    """The alliance start ping ("INCOMING PING TRANSMISSION..."), with the
    campaign as the audience. A coordinator's server gets the campaign page
    for "View Fleet Information", since the fleet page is members only."""
    # pylint: disable-next=import-outside-toplevel
    from fleets.notifications import get_fleet_discord_notification

    fc = fleet.fleet_commander
    alt = fleet.fleet_commander_alt
    location = fleet.formup_location
    payload = get_fleet_discord_notification(
        fleet_id=fleet.id,
        fleet_type=fleet.get_type_display(),
        fleet_location=location.location_name if location else "Ask FC",
        fleet_audience=fleet.campaign.name,
        fleet_commander_name=fc.character_name if fc else "",
        fleet_commander_id=fc.character_id if fc else 0,
        fleet_commander_in_game_name=alt.character_name if alt else None,
        fleet_description=fleet.description or fleet.objective,
        fleet_voice_channel=None,
        fleet_voice_channel_link=None,
        content="@everyone",
    )
    if relay:
        for button in payload["components"][0]["components"]:
            if button["label"] == "View Fleet Information":
                button["url"] = campaign_url(fleet.campaign, "fleets")
    payload["allowed_mentions"] = EVERYONE
    return payload


# --- Sending -------------------------------------------------------------


def _queue(destination: Destination, payload: dict, context: str) -> None:
    # pylint: disable-next=import-outside-toplevel
    from discord.outbox import queue_channel_message

    queue_channel_message(
        destination.channel_id, payload=payload, context=context
    )


def announce_structure(structure: CampaignStructure) -> None:
    for destination in destinations(structure.campaign, INTEL, "structures"):
        _queue(
            destination,
            structure_intel(structure),
            f"campaign {structure.campaign_id} structure {structure.id}",
        )


def announce_timer(campaign: Campaign, timer) -> None:
    for destination in destinations(campaign, INTEL, "timers"):
        _queue(
            destination,
            timer_intel(campaign, timer),
            f"campaign {campaign.id} timer {timer.id}",
        )


def announce_fleet(fleet) -> None:
    if fleet.campaign_id is None or fleet.invite_only:
        return
    for destination in destinations(fleet.campaign, FLEETS):
        _queue(
            destination,
            fleet_ping(fleet, destination.relay),
            f"campaign {fleet.campaign_id} fleet {fleet.id} ping",
        )


def has_board(campaign: Campaign, kind: str) -> bool:
    return (
        bool(destinations(campaign, kind))
        or campaign.discord_boards.filter(kind=kind).exists()
    )


def queue_board_refresh(campaign_id: int, kind: str) -> None:
    """Refresh one board after the transaction commits."""
    # pylint: disable=import-outside-toplevel
    from campaigns.tasks import refresh_campaign_board
    from discord.outbox import on_commit_enqueue

    on_commit_enqueue(
        refresh_campaign_board,
        (campaign_id, kind),
        context=f"campaign {campaign_id} {kind} board",
        countdown=2,
    )


def queue_all_board_refreshes(campaign_id: int) -> None:
    """After channels change: post the boards to new channels and take
    them out of channels no longer picked."""
    for kind in (TIMERS, SCHEDULE):
        queue_board_refresh(campaign_id, kind)


BUILDERS = {TIMERS: timerboard, SCHEDULE: schedule}


def _hash(payload: dict) -> str:
    # The "Updated" footer changes every run; leave it out of the hash.
    stable = dict(payload)
    stable["content"] = payload["content"].rsplit("\n-# Updated", 1)[0]
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True).encode()
    ).hexdigest()


def refresh_board(campaign: Campaign, kind: str, client=None) -> int:
    """Bring every ``kind`` board of the campaign up to date. Returns how
    many messages were posted or edited."""
    # pylint: disable-next=import-outside-toplevel
    from discord.client import DiscordClient

    client = client or DiscordClient()
    if campaign.status not in POSTING_STATUSES:
        # A finished campaign keeps its last boards as they were.
        return 0
    wanted = destinations(campaign, kind)
    _drop_unused(campaign, kind, {d.channel_id for d in wanted}, client)
    if not wanted:
        return 0
    payload = BUILDERS[kind](campaign)
    changed = 0
    for destination in wanted:
        try:
            if _upsert(
                campaign, destination.channel_id, kind, payload, client
            ):
                changed += 1
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning(
                "Campaign %s: could not update the %s board in channel %s",
                campaign.id,
                kind,
                destination.channel_id,
                exc_info=True,
            )
    return changed


def _upsert(campaign, channel_id: int, kind: str, payload, client) -> bool:
    board, _ = CampaignDiscordBoard.objects.get_or_create(
        campaign=campaign, channel_id=channel_id, kind=kind
    )
    digest = _hash(payload)
    if board.message_id and board.content_hash == digest:
        return False
    if board.message_id:
        try:
            client.update_message(
                channel_id, board.message_id, payload=payload
            )
            board.content_hash = digest
            board.save(update_fields=["content_hash", "updated_at"])
            return True
        except HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            # Someone deleted the message: post a new one.
    message = client.create_message(channel_id, payload=payload).json()
    board.message_id = int(message["id"])
    board.content_hash = digest
    board.save(update_fields=["message_id", "content_hash", "updated_at"])
    return True


def _drop_unused(campaign, kind: str, keep: set[int], client) -> None:
    """Forget boards in channels no longer picked, and delete their message."""
    stale = campaign.discord_boards.filter(kind=kind).exclude(
        channel_id__in=keep
    )
    for board in stale:
        if board.message_id:
            try:
                client.delete_message(board.channel_id, board.message_id)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.info(
                    "Campaign %s: old %s board %s already gone",
                    campaign.id,
                    kind,
                    board.message_id,
                )
        board.delete()
