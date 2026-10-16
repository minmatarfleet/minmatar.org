"""Attach feed killmails to a tracked fleet.

A killmail belongs to a fleet instance when one of its attackers, or its
victim, was in that fleet when the ship died. Membership comes from the ESI
fleet poller: ``join_time`` is when a pilot first appeared and ``updated_at``
is rewritten on every pass, so it is the pilot's last-seen time. Bounding by
those two keeps a pilot who left early, or joined late, from claiming kills
they were not there for.

Only killmails the feed stored are visible here, so a fleet that roams
outside the monitored systems will be missing those kills.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.utils import timezone
from eveuniverse.models import EveSolarSystem

from feed.helpers.eve_names import (
    KNOWN_CAPSULE_TYPE_IDS,
    resolve_character_names,
    resolve_type_names,
)
from feed.models import FeedKillmail

# ESI polls the fleet every few minutes, so a pilot can die or get on a mail
# a little before their row is first written or after it was last touched.
JOIN_GRACE = timedelta(minutes=2)
LAST_SEEN_GRACE = timedelta(minutes=5)

OUTCOME_KILL = "kill"
OUTCOME_LOSS = "loss"

HEADLINE_LIMIT = 5

# Capsule and Capsule - Genolution.
CAPSULE_TYPE_IDS = KNOWN_CAPSULE_TYPE_IDS | {33328}


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
    # Imported here so feed.helpers does not load fleets at import time.
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstanceMember

    windows: dict[int, tuple[datetime, datetime]] = {}
    rows = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance=instance
    ).values_list("character_id", "join_time", "updated_at")
    for character_id, joined, last_seen in rows:
        last_seen = last_seen or joined
        if character_id in windows:
            prior_joined, prior_seen = windows[character_id]
            joined = min(joined, prior_joined)
            last_seen = max(last_seen, prior_seen)
        windows[character_id] = (joined, last_seen)
    return windows


def _in_fleet(
    windows: dict[int, tuple[datetime, datetime]],
    character_id: int | None,
    moment: datetime,
) -> bool:
    if not character_id or character_id not in windows:
        return False
    joined, last_seen = windows[character_id]
    return joined - JOIN_GRACE <= moment <= last_seen + LAST_SEEN_GRACE


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


def match_fleet_killmails(instance) -> FleetKillSummary:
    """Every feed killmail one of this instance's pilots was on."""
    windows = _member_windows(instance)
    if not windows:
        return FleetKillSummary()

    start, end = _instance_bounds(instance, windows)
    matched: list[FleetKillmail] = []
    for killmail in FeedKillmail.objects.filter(
        killmail_time__gte=start, killmail_time__lte=end
    ).order_by("killmail_time", "killmail_id"):
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
        matched.append(
            FleetKillmail(
                killmail_id=killmail.killmail_id,
                killmail_time=moment,
                outcome=outcome,
                solar_system_id=killmail.solar_system_id,
                victim_ship_type_id=killmail.victim_ship_type_id,
                victim_character_id=killmail.victim_character_id,
                isk_value=int(
                    (killmail.zkb_meta or {}).get("totalValue") or 0
                ),
                fleet_pilots=len(pilots),
                is_capsule=killmail.victim_ship_type_id in CAPSULE_TYPE_IDS,
            )
        )
    _attach_names(matched)
    return FleetKillSummary(killmails=matched)


def _attach_names(killmails: list[FleetKillmail]) -> None:
    if not killmails:
        return
    system_ids = {k.solar_system_id for k in killmails}
    systems = dict(
        EveSolarSystem.objects.filter(id__in=system_ids).values_list(
            "id", "name"
        )
    )
    ships = resolve_type_names(k.victim_ship_type_id for k in killmails)
    pilots = resolve_character_names(k.victim_character_id for k in killmails)
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
        if event is not None and instance.end_time is not None:
            instance_rows = (event.payload or {}).get("killmails") or []
        else:
            instance_rows = [
                k.as_payload()
                for k in match_fleet_killmails(instance).killmails
            ]
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
