"""Attach feed killmails to a tracked fleet.

A killmail belongs to a fleet instance when one of its attackers, or its
victim, was in that fleet when the ship died. Presence windows come from
fleets.helpers.presence, which the campaign board shares, so a pilot who left
early, or joined late, cannot claim kills they were not there for.

Only killmails the feed stored are visible here, so a fleet that roams
outside the monitored systems will be missing those kills.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from django.utils import timezone
from eveonline.helpers.corporations.safe_cache import cache_get, cache_set
from eveonline.killmail_classes import CAPSULE_TYPE_IDS
from eveuniverse.models import EveSolarSystem

from feed.helpers.eve_names import (
    resolve_character_names,
    resolve_type_names,
)
from feed.models import FeedKillmail
from fleets.helpers.presence import (
    JOIN_GRACE,
    LAST_SEEN_GRACE,
    member_window,
    was_present,
)

logger = logging.getLogger(__name__)

OUTCOME_KILL = "kill"
OUTCOME_LOSS = "loss"

HEADLINE_LIMIT = 5

# The fleet page matches live when no settled card exists. Cache it so an
# old fleet does not ask ESI for victim names on every view.
LIVE_CACHE_OPEN_SECONDS = 60
LIVE_CACHE_ENDED_SECONDS = 60 * 60


@dataclass
class FleetKillmail:
    killmail_id: int
    killmail_time: datetime
    outcome: str
    solar_system_id: int
    victim_ship_type_id: int | None
    victim_character_id: int | None
    isk_value: int
    fleet_pilots: int
    is_capsule: bool
    solar_system_name: str = ""
    victim_ship_name: str = ""
    victim_character_name: str = ""

    def as_payload(self) -> dict:
        return {
            "killmail_id": self.killmail_id,
            "killmail_time": self.killmail_time.isoformat(),
            "outcome": self.outcome,
            "solar_system_id": self.solar_system_id,
            "solar_system_name": self.solar_system_name,
            "victim_ship_type_id": self.victim_ship_type_id,
            "victim_ship_name": self.victim_ship_name,
            "victim_character_id": self.victim_character_id,
            "victim_character_name": self.victim_character_name,
            "isk_value": self.isk_value,
            "fleet_pilots": self.fleet_pilots,
            "is_capsule": self.is_capsule,
        }


@dataclass
class FleetKillSummary:
    killmails: list[FleetKillmail] = field(default_factory=list)

    @property
    def kills(self) -> list[FleetKillmail]:
        return [k for k in self.killmails if k.outcome == OUTCOME_KILL]

    @property
    def losses(self) -> list[FleetKillmail]:
        return [k for k in self.killmails if k.outcome == OUTCOME_LOSS]

    @property
    def last_killmail_at(self) -> datetime | None:
        if not self.killmails:
            return None
        return max(k.killmail_time for k in self.killmails)


def summary_totals(killmails: list[dict]) -> dict:
    """Totals over payload rows; pods count towards ISK, not ships."""
    kills = [k for k in killmails if k["outcome"] == OUTCOME_KILL]
    losses = [k for k in killmails if k["outcome"] == OUTCOME_LOSS]
    return {
        "isk_destroyed": sum(k["isk_value"] for k in kills),
        "isk_lost": sum(k["isk_value"] for k in losses),
        "ships_destroyed": sum(1 for k in kills if not k["is_capsule"]),
        "pods_destroyed": sum(1 for k in kills if k["is_capsule"]),
        "ships_lost": sum(1 for k in losses if not k["is_capsule"]),
        "pods_lost": sum(1 for k in losses if k["is_capsule"]),
    }


def _member_windows(instance) -> dict[int, tuple[datetime, datetime]]:
    # Imported here so feed.helpers does not load fleets.models at import
    # time.
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstanceMember

    windows: dict[int, tuple[datetime, datetime]] = {}
    rows = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance=instance
    ).values_list("character_id", "join_time", "created_at", "updated_at")
    for character_id, join_time, created_at, updated_at in rows:
        joined, last_seen = member_window(join_time, created_at, updated_at)
        if character_id in windows:
            prior_joined, prior_seen = windows[character_id]
            joined = min(joined, prior_joined)
            last_seen = max(last_seen, prior_seen)
        windows[character_id] = (joined, last_seen)
    return windows


# Public for the fleet fight timeline, which reads the same windows.
def member_windows(instance) -> dict[int, tuple[datetime, datetime]]:
    return _member_windows(instance)


def _in_fleet(
    windows: dict[int, tuple[datetime, datetime]],
    character_id: int | None,
    moment: datetime,
) -> bool:
    if not character_id or character_id not in windows:
        return False
    return was_present(windows[character_id], moment)


def _instance_bounds(
    instance, windows: dict[int, tuple[datetime, datetime]]
) -> tuple[datetime, datetime]:
    start = instance.start_time - JOIN_GRACE
    # The latest member sighting bounds a fleet whose end was never
    # recorded, so a stale open instance does not scan forever.
    last_seen = max(seen for _, seen in windows.values())
    end = last_seen
    if instance.end_time:
        end = min(end, instance.end_time)
    return start, min(end + LAST_SEEN_GRACE, timezone.now())


@dataclass
class InstanceKillmail:
    """A feed killmail one of the instance's pilots was on, before naming."""

    killmail: FeedKillmail
    outcome: str
    # In-fleet attackers; empty on a loss nobody in fleet shot back on.
    pilots: set[int]


def iter_instance_killmails(instance, windows=None):
    """Yield every feed killmail this instance's pilots were on, in order.

    A loss when the victim was in fleet at that moment, otherwise a kill when
    any attacker was. ``windows`` defaults to the instance's member windows.
    """
    windows = _member_windows(instance) if windows is None else windows
    if not windows:
        return
    start, end = _instance_bounds(instance, windows)
    # The raw mail is the heaviest column and matching never reads it.
    for killmail in (
        FeedKillmail.objects.filter(
            killmail_time__gte=start, killmail_time__lte=end
        )
        .defer("raw_killmail")
        .order_by("killmail_time", "killmail_id")
    ):
        moment = killmail.killmail_time
        pilots = {
            attacker.get("character_id")
            for attacker in killmail.attacker_summary or []
            if _in_fleet(windows, attacker.get("character_id"), moment)
        }
        if _in_fleet(windows, killmail.victim_character_id, moment):
            outcome = OUTCOME_LOSS
        elif pilots:
            outcome = OUTCOME_KILL
        else:
            continue
        yield InstanceKillmail(
            killmail=killmail, outcome=outcome, pilots=pilots
        )


def killmail_isk(killmail: FeedKillmail) -> int:
    return int((killmail.zkb_meta or {}).get("totalValue") or 0)


def match_fleet_killmails(
    instance, known: dict[int, dict] | None = None
) -> FleetKillSummary:
    """Every feed killmail one of this instance's pilots was on.

    ``known`` maps killmail id to a previously stored payload row; its names
    are reused so a re-run does not ask ESI about the same victims again.
    """
    matched: list[FleetKillmail] = []
    for row in iter_instance_killmails(instance):
        killmail = row.killmail
        matched.append(
            FleetKillmail(
                killmail_id=killmail.killmail_id,
                killmail_time=killmail.killmail_time,
                outcome=row.outcome,
                solar_system_id=killmail.solar_system_id,
                victim_ship_type_id=killmail.victim_ship_type_id,
                victim_character_id=killmail.victim_character_id,
                isk_value=killmail_isk(killmail),
                fleet_pilots=len(row.pilots),
                is_capsule=killmail.victim_ship_type_id in CAPSULE_TYPE_IDS,
            )
        )
    _attach_names(matched, known or {})
    return FleetKillSummary(killmails=matched)


def _attach_names(
    killmails: list[FleetKillmail], known: dict[int, dict]
) -> None:
    if not killmails:
        return
    system_ids = {k.solar_system_id for k in killmails}
    systems = dict(
        EveSolarSystem.objects.filter(id__in=system_ids).values_list(
            "id", "name"
        )
    )
    ships = resolve_type_names(k.victim_ship_type_id for k in killmails)

    pilots: dict[int, str] = {}
    unnamed: set[int] = set()
    for killmail in killmails:
        stored = (known.get(killmail.killmail_id) or {}).get(
            "victim_character_name"
        )
        if stored:
            pilots[killmail.victim_character_id] = stored
        elif killmail.victim_character_id:
            unnamed.add(killmail.victim_character_id)
    try:
        pilots.update(resolve_character_names(unnamed - pilots.keys()))
    except Exception:  # pylint: disable=broad-exception-caught
        # Victim names are cosmetic; an ESI outage must not drop the card.
        logger.warning("Could not resolve fleet kill victim names")

    for killmail in killmails:
        killmail.solar_system_name = systems.get(
            killmail.solar_system_id, f"System {killmail.solar_system_id}"
        )
        killmail.victim_ship_name = ships.get(killmail.victim_ship_type_id, "")
        killmail.victim_character_name = pilots.get(
            killmail.victim_character_id, ""
        )


def build_fleet_kills_payload(instance, summary: FleetKillSummary) -> dict:
    """The stored shape: the fleet page and the feed card both read it."""
    rows = [k.as_payload() for k in summary.killmails]
    headline = sorted(
        (
            row
            for row in rows
            if row["outcome"] == OUTCOME_KILL and not row["is_capsule"]
        ),
        key=lambda row: row["isk_value"],
        reverse=True,
    )[:HEADLINE_LIMIT]
    systems: dict[int, str] = {}
    for row in rows:
        systems.setdefault(row["solar_system_id"], row["solar_system_name"])
    return {
        "fleet_id": instance.eve_fleet_id,
        "fleet_instance_id": instance.id,
        "systems": [
            {"system_id": system_id, "system_name": name}
            for system_id, name in systems.items()
        ],
        "headline": [row["killmail_id"] for row in headline],
        "killmails": rows,
        **summary_totals(rows),
    }


def stored_killmail_rows(event) -> dict[int, dict]:
    """Payload rows of a stored fleet_kills card, by killmail id."""
    if event is None:
        return {}
    return {
        row["killmail_id"]: row
        for row in (event.payload or {}).get("killmails") or []
    }


def _live_rows(instance, known: dict[int, dict]) -> list[dict]:
    key = f"feed:fleet_kills:live:{instance.id}"
    rows = cache_get(key)
    if rows is None:
        rows = [
            k.as_payload()
            for k in match_fleet_killmails(instance, known).killmails
        ]
        cache_set(
            key,
            rows,
            (
                LIVE_CACHE_OPEN_SECONDS
                if instance.end_time is None
                else LIVE_CACHE_ENDED_SECONDS
            ),
        )
    return rows


def fleet_kill_report(fleet) -> dict:
    """Kills and losses across every instance of a fleet.

    A finished instance reads the stored ``fleet_kills`` event, which
    outlives the 30-day killmail purge. An open one, or one the rollup has
    not reached yet, is matched live.
    """
    # pylint: disable=import-outside-toplevel
    from feed.models import FeedEventFleetLink
    from fleets.models import EveFleetInstance

    instances = list(EveFleetInstance.objects.filter(eve_fleet=fleet))
    stored = {
        link.fleet_instance_id: link.feed_event
        for link in FeedEventFleetLink.objects.filter(
            fleet_instance_id__in=[instance.id for instance in instances],
            feed_event__rollup_code="fleet_kills",
        ).select_related("feed_event")
    }

    rows: dict[int, dict] = {}
    for instance in instances:
        event = stored.get(instance.id)
        known = stored_killmail_rows(event)
        if event is not None and instance.end_time is not None:
            instance_rows = list(known.values())
        else:
            instance_rows = _live_rows(instance, known)
        for row in instance_rows:
            rows.setdefault(row["killmail_id"], row)

    killmails = sorted(
        rows.values(),
        key=lambda row: (row["killmail_time"], row["killmail_id"]),
        reverse=True,
    )
    return {
        "fleet_id": fleet.id,
        "tracked": bool(instances),
        "killmails": killmails,
        **summary_totals(killmails),
    }
