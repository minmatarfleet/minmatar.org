"""Discord pieces of a private fleet: the invite DM, its edits, and the
private coordination thread.

The thread is a private Discord thread (not invitable) under the fleet
audience's channel, #pings for the alliance audience, or
DISCORD_PRIVATE_FLEET_CHANNEL_ID when set. The bot adds the FC, every
Strategic FC and each pilot who says I'm in; the start ping posts there with
@everyone, which in a thread reaches only its members.

The Sitting out button is handled by the bot; its prefix must match
bot/app/custom_ids.py (backend/discord/test_bot_custom_ids.py checks it).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.db.models import Q

from app.links import fleet_url
from discord.client import PRIVATE_THREAD
from fleets.helpers.private_fleets import OPSEC_LINE, target_progress

logger = logging.getLogger(__name__)

SIT_OUT_CUSTOM_ID_PREFIX = "fleet_invite:out:"

_ACTION_ROW = 1
_BUTTON = 2
_STYLE_SECONDARY = 2
_STYLE_LINK = 5
# The fleet ping red.
_COLOR = 0xB53620
_COLOR_IN = 0x23A55A
_COLOR_DONE = 0x4E5058


def sit_out_custom_id(invite_id: int) -> str:
    return f"{SIT_OUT_CUSTOM_ID_PREFIX}{int(invite_id)}"


def _link(label: str, url: str) -> dict:
    return {"type": _BUTTON, "style": _STYLE_LINK, "label": label, "url": url}


def _sit_out_button(invite_id: int) -> dict:
    return {
        "type": _BUTTON,
        "style": _STYLE_SECONDARY,
        "label": "Sitting out",
        "custom_id": sit_out_custom_id(invite_id),
    }


def _row(*buttons) -> list[dict]:
    buttons = [b for b in buttons if b]
    return [{"type": _ACTION_ROW, "components": buttons}] if buttons else []


def _eve_time(value) -> str:
    return value.strftime("%a %d %b, %H:%M EVE")


def _discord_time(value) -> str:
    return f"<t:{int(value.timestamp())}:F>"


def _fc_name(fleet) -> str:
    fc = fleet.fleet_commander
    if fc:
        return fc.character_name
    return fleet.created_by.username if fleet.created_by else "The FC"


def fleet_title(fleet) -> str:
    return fleet.objective or fleet.description[:80] or f"Fleet {fleet.id}"


def thread_url(fleet) -> str | None:
    if not fleet.discord_thread_id:
        return None
    return (
        f"https://discord.com/channels/{settings.DISCORD_GUILD_ID}/"
        f"{fleet.discord_thread_id}"
    )


def _character_names(user_id: int) -> str:
    # pylint: disable=import-outside-toplevel
    from eveonline.models import EveCharacter

    names = list(
        EveCharacter.objects.filter(user_id=user_id)
        .order_by("character_name")
        .values_list("character_name", flat=True)[:6]
    )
    return ", ".join(names)


def _wanted(fleet) -> str:
    return " · ".join(
        f"{row['target']} {row['name']}" for row in target_progress(fleet)
    )


def invite_embed(invite, *, reminder: bool = False) -> dict:
    fleet = invite.eve_fleet
    fields = [
        {
            "name": "When",
            "value": f"{_eve_time(fleet.start_time)}\n"
            f"{_discord_time(fleet.start_time)}",
            "inline": True,
        },
        {
            "name": "Form-up",
            "value": (
                fleet.formup_location.location_name
                if fleet.formup_location
                else "Ask FC"
            ),
            "inline": True,
        },
    ]
    if fleet.doctrine_id:
        fields.append(
            {"name": "Doctrine", "value": fleet.doctrine.name, "inline": True}
        )
    names = _character_names(invite.user_id)
    if names:
        fields.append(
            {"name": "Your characters", "value": names, "inline": True}
        )
    wanted = _wanted(fleet)
    if wanted:
        fields.append({"name": "Wanted", "value": wanted, "inline": False})
    note = invite.wave.note
    description = (
        f"**{_fc_name(fleet)}** is inviting you to a private "
        f"{fleet.get_type_display()}."
    )
    if note:
        description += f"\n> {note}"
    description += f"\n\n🔒 **{OPSEC_LINE}**"
    title = f"You're invited: {fleet_title(fleet)}"
    if reminder:
        title = f"Still coming? {fleet_title(fleet)}"
    return {
        "author": {"name": "Fleets · Private"},
        "title": title,
        "url": fleet_url(fleet.id),
        "description": description,
        "fields": fields,
        "color": _COLOR,
    }


def invite_payload(invite, *, reminder: bool = False) -> dict:
    return {
        "embeds": [invite_embed(invite, reminder=reminder)],
        "components": _row(
            _link("I'm in: pick ships", fleet_url(invite.eve_fleet_id)),
            _sit_out_button(invite.id),
        ),
    }


def answered_payload(invite) -> dict:
    """What the invite DM is edited to once something changes."""
    fleet = invite.eve_fleet
    title = fleet_title(fleet)
    page = fleet_url(fleet.id)
    if fleet.status == "cancelled":
        return {
            "embeds": [
                {
                    "author": {"name": "Fleets · Private"},
                    "title": "This fleet was cancelled",
                    "description": f"{_fc_name(fleet)} cancelled {title}. "
                    "Keep it quiet all the same.",
                    "color": _COLOR_DONE,
                }
            ],
            "components": [],
        }
    if fleet.status in ("active", "complete"):
        return {
            "embeds": [
                {
                    "author": {"name": "Fleets · Private"},
                    "title": f"This fleet has started: {title}",
                    "url": page,
                    "color": _COLOR_DONE,
                }
            ],
            "components": _row(
                _link("View Fleet Information", page),
            ),
        }
    if invite.answer == invite.ANSWER_IN:
        ships = _signed_up(invite)
        description = (
            f"{_eve_time(fleet.start_time)}. You're in the private thread, "
            "where the FC coordinates and the start ping goes."
        )
        if ships:
            description += "\nYou're bringing:\n" + ships
        description += f"\n\n🔒 **{OPSEC_LINE}**"
        url = thread_url(fleet)
        return {
            "embeds": [
                {
                    "author": {"name": "Fleets · Private"},
                    "title": f"You're in: {title}",
                    "url": page,
                    "description": description,
                    "color": _COLOR_IN,
                }
            ],
            "components": _row(
                _link("Open coordination thread", url) if url else None,
                _link("Change ships", page),
                _sit_out_button(invite.id),
            ),
        }
    if invite.answer == invite.ANSWER_OUT:
        return {
            "embeds": [
                {
                    "author": {"name": "Fleets · Private"},
                    "title": "You're sitting this one out",
                    "description": f"{title}, {_eve_time(fleet.start_time)}. "
                    "Changed your mind? I'm in still works until the fleet "
                    f"starts.\n\n🔒 **{OPSEC_LINE}**",
                    "color": _COLOR_DONE,
                }
            ],
            "components": _row(_link("I'm in: pick ships", page)),
        }
    return invite_payload(invite)


def _signed_up(invite) -> str:
    # pylint: disable=import-outside-toplevel
    from eveonline.models import EveCharacter
    from fleets.models import EveFleetShipVolunteer

    character_ids = list(
        EveCharacter.objects.filter(user_id=invite.user_id).values_list(
            "character_id", flat=True
        )
    )
    lines = []
    for volunteer in EveFleetShipVolunteer.objects.filter(
        eve_fleet_id=invite.eve_fleet_id, character_id__in=character_ids
    ).select_related("fitting", "fleet_fitting"):
        ship = volunteer.ship_name
        if volunteer.fitting_id:
            ship = volunteer.fitting.name
        elif volunteer.fleet_fitting_id:
            ship = volunteer.fleet_fitting.name
        lines.append(f"**{volunteer.character_name}** · {ship}")
    return "\n".join(lines)


def send_invite_dm(client, invite, *, reminder: bool = False) -> bool:
    """DM one invite (Celery only) and keep the message id, so the DM can be
    edited once the pilot answers. Not routed through notify_user: an invite
    can't be muted and must carry its own buttons."""
    # pylint: disable=import-outside-toplevel
    from django.utils import timezone

    from discord.models import DiscordUser

    discord_user = DiscordUser.objects.filter(user_id=invite.user_id).first()
    if discord_user is None:
        invite.dm_delivered = False
        invite.save(update_fields=["dm_delivered"])
        return False
    try:
        message = client.send_dm(
            str(discord_user.id),
            payload=invite_payload(invite, reminder=reminder),
        ).json()
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Could not DM private fleet invite %s", invite.id, exc_info=True
        )
        if not reminder:
            invite.dm_delivered = False
            invite.sent_at = timezone.now()
            invite.save(update_fields=["dm_delivered", "sent_at"])
        return False
    invite.dm_delivered = True
    invite.dm_channel_id = int(message["channel_id"])
    invite.dm_message_id = int(message["id"])
    fields = ["dm_delivered", "dm_channel_id", "dm_message_id"]
    if not reminder:
        invite.sent_at = timezone.now()
        fields.append("sent_at")
    invite.save(update_fields=fields)
    return True


# --- The coordination thread -----------------------------------------------


def thread_parent_channel_id(fleet) -> int | None:
    override = getattr(settings, "DISCORD_PRIVATE_FLEET_CHANNEL_ID", None)
    if override:
        return int(override)
    if fleet.audience and fleet.audience.discord_channel_id:
        return int(fleet.audience.discord_channel_id)
    return None


def thread_name(fleet) -> str:
    """A plain name: thread names show in the server audit log."""
    return f"Op {fleet.id}"


def strategic_fc_user_ids() -> set[int]:
    """Users holding the Strategic FC permission (fleets.manage_any)."""
    perm = Permission.objects.filter(
        codename="manage_any_fleet", content_type__app_label="fleets"
    ).first()
    if perm is None:
        return set()
    return set(
        User.objects.filter(is_active=True)
        .filter(Q(user_permissions=perm) | Q(groups__permissions=perm))
        .values_list("id", flat=True)
        .distinct()
    )


def summary_payload(fleet) -> dict:
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.private_fleets import invite_totals

    totals = invite_totals(fleet)
    fields = [
        {
            "name": row["name"],
            "value": f"{row['have']} / {row['target']}",
            "inline": True,
        }
        for row in target_progress(fleet)
    ]
    location = (
        fleet.formup_location.location_name
        if fleet.formup_location
        else "Ask FC"
    )
    return {
        "embeds": [
            {
                "author": {"name": "Fleets · Private"},
                "title": fleet_title(fleet),
                "url": fleet_url(fleet.id),
                "description": (
                    f"{_eve_time(fleet.start_time)} "
                    f"{_discord_time(fleet.start_time)} · {location} · "
                    f"FC {_fc_name(fleet)}\n"
                    f"{_count(totals['in'], 'player is', 'players are')} in "
                    f"with {_count(totals['characters_in'], 'character')}."
                    "\n\n"
                    f"🔒 **{OPSEC_LINE}**"
                ),
                "fields": fields,
                "color": _COLOR,
            }
        ],
        "components": _row(
            _link("View Fleet Information", fleet_url(fleet.id)),
            _link("Change my ships", fleet_url(fleet.id)),
        ),
    }


def _count(number: int, one: str, many: str = "") -> str:
    """'1 player is', '3 players are'; '1 character', '2 characters'."""
    return f"{number} {one if number == 1 else (many or one + 's')}"


def is_private_thread(client, thread_id) -> bool:
    """Guard for @everyone: only ever post it into a private thread."""
    try:
        channel = client.get_channel(thread_id)
    except Exception:  # pylint: disable=broad-except
        logger.warning("Could not read thread %s", thread_id, exc_info=True)
        return False
    return int(channel.get("type", -1)) == PRIVATE_THREAD


def thread_start_ping_payload(ping_payload: dict) -> dict:
    """The usual start ping, for a private thread: @everyone (thread
    members only) and the audience reading Private."""
    payload = dict(ping_payload)
    payload["content"] = "@everyone"
    payload["allowed_mentions"] = {"parse": ["everyone"]}
    embeds = []
    for embed in payload.get("embeds") or []:
        embed = dict(embed)
        description = embed.get("description") or ""
        lines = [
            (
                "**AUDIENCE**: PRIVATE · INVITE ONLY"
                if line.startswith("**AUDIENCE**")
                else line
            )
            for line in description.split("\n")
        ]
        embed["description"] = "\n".join(lines)
        embeds.append(embed)
    if embeds:
        payload["embeds"] = embeds
    return payload
