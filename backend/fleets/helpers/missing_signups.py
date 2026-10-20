"""
Pilots who signed up a ship for a live fleet but are not in it yet, and the
FC's one-click Discord nudge to them.

The nudge sends one DM per player (a multiboxer gets one message listing
their characters), runs in Celery so the request never waits on Discord,
and is limited to one send per fleet per NUDGE_COOLDOWN. Results are kept
in the cache so the fleet page can say how many it reached.
"""

import logging
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from app.links import site_url
from discord.client import DiscordClient
from discord.models import DiscordUser
from eveonline.helpers.corporations.safe_cache import (
    cache_add,
    cache_get,
    cache_set,
)
from eveonline.models import EveCharacter

from fleets.helpers.composition import fleet_composition
from fleets.helpers.role_coverage import _present_members

logger = logging.getLogger(__name__)

NUDGE_COOLDOWN = timedelta(minutes=15)
NUDGE_RESULT_TTL = 6 * 60 * 60


def _cooldown_key(fleet_id: int) -> str:
    return f"fleets:nudge:cooldown:{fleet_id}"


def _result_key(fleet_id: int) -> str:
    return f"fleets:nudge:result:{fleet_id}"


def live_instance(fleet):
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance

    return (
        EveFleetInstance.objects.filter(eve_fleet=fleet, end_time__isnull=True)
        .order_by("-start_time")
        .first()
    )


def missing_signups(fleet) -> list[dict]:
    """Ship volunteers whose character the poller has not seen in fleet."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetShipVolunteer

    instance = live_instance(fleet)
    if not instance or not instance.last_updated:
        return []
    present = {m.character_id for m in _present_members(fleet, lambda _: True)}
    by_key = {entry.key: entry for entry in fleet_composition(fleet)}

    rows = []
    for volunteer in EveFleetShipVolunteer.objects.filter(
        eve_fleet=fleet
    ).order_by("character_name"):
        if volunteer.character_id in present:
            continue
        entry = by_key.get(volunteer.target_key)
        rows.append(
            {
                "character_id": volunteer.character_id,
                "character_name": volunteer.character_name,
                "ship_name": (
                    entry.ship_name if entry else volunteer.ship_name
                ),
                "cyno": bool(entry and entry.roles.cyno),
            }
        )
    return rows


def nudge_state(fleet_id: int) -> dict:
    """Last nudge result and when the next one is allowed (None = now)."""
    result = cache_get(_result_key(fleet_id))
    next_at = cache_get(_cooldown_key(fleet_id))
    return {"last": result, "next_allowed_at": next_at}


def claim_nudge(fleet_id: int) -> bool:
    """Start the cooldown; False if one is running (or the cache is down)."""
    next_at = timezone.now() + NUDGE_COOLDOWN
    return cache_add(
        _cooldown_key(fleet_id),
        next_at,
        int(NUDGE_COOLDOWN.total_seconds()),
    )


def _fleet_url(fleet) -> str:
    return site_url(f"/fleets/upcoming/{fleet.id}")


def build_nudge_message(fleet, characters: list[dict]) -> str:
    fc = fleet.fleet_commander
    fc_name = fc.character_name if fc else "The FC"
    location = fleet.formup_location
    system = location.short_name if location else "staging"
    pilots = ", ".join(
        (
            f"{c['character_name']} ({c['ship_name']})"
            if c["ship_name"]
            else c["character_name"]
        )
        for c in characters
    )
    title = fleet.objective or f"fleet {fleet.id}"
    return "\n".join(
        [
            f"**{title}** is live and you signed up: {pilots}.",
            f"{fc_name} hasn't seen you in fleet yet. X up in {system} "
            "local or ask for an invite in fleet comms.",
            _fleet_url(fleet),
        ]
    )


def send_missing_signup_nudges(fleet) -> dict:
    """DM each player with signed-up characters not in fleet; one DM each."""
    rows = missing_signups(fleet)
    users = dict(
        EveCharacter.objects.filter(
            character_id__in=[r["character_id"] for r in rows]
        ).values_list("character_id", "user_id")
    )
    by_user = defaultdict(list)
    unlinked = 0
    for row in rows:
        user_id = users.get(row["character_id"])
        if user_id is None:
            unlinked += 1
            continue
        by_user[user_id].append(row)

    discord_ids = dict(
        DiscordUser.objects.filter(user_id__in=by_user.keys()).values_list(
            "user_id", "id"
        )
    )
    client = DiscordClient()
    delivered = failed = 0
    for user_id, characters in by_user.items():
        discord_id = discord_ids.get(user_id)
        if not discord_id:
            failed += 1
            continue
        try:
            client.send_dm(
                str(discord_id),
                message=build_nudge_message(fleet, characters),
            )
            delivered += 1
        except Exception:  # pylint: disable=broad-exception-caught
            # Closed DMs (50007) and the like: count it, keep going.
            logger.info(
                "Nudge DM to user %s for fleet %s failed",
                user_id,
                fleet.id,
                exc_info=True,
            )
            failed += 1

    result = {
        "sent_at": timezone.now().isoformat(),
        "players": len(by_user),
        "delivered": delivered,
        "failed": failed + unlinked,
    }
    cache_set(_result_key(fleet.id), result, NUDGE_RESULT_TTL)
    return result
