"""Structure browser: alliance locations (EveLocation) with descriptions,
fittings, audiences, pilot submissions and a change history.

Pure parsing lives at the top so it is easy to test; database and ESI work
follows."""

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from eveonline.client import EsiClient
from eveonline.models import (
    EveCharacter,
    EveCharacterAsset,
    EveCharacterClone,
    EveLocation,
)
from groups.helpers.feature_access import can_use_feature

from .models import (
    EveStructure,
    LocationAudienceGroup,
    LocationChange,
    LocationSubmission,
)

logger = logging.getLogger(__name__)

MANAGE_FEATURE = "structures.locations.manage"
VIEW_FEATURE = "structures.view"
GOOD_FOR_CHOICES = ("industry", "clones", "logistics")

# Upwell structure type ids, for the type badge and card art.
STRUCTURE_TYPE_NAMES = {
    35832: "Astrahus",
    35833: "Fortizar",
    35834: "Keepstar",
    35825: "Raitaru",
    35826: "Azbel",
    35827: "Sotiyo",
    35835: "Athanor",
    35836: "Tatara",
}

SERVICE_WORDS = (
    "Manufacturing Plant",
    "Shipyard",
    "Invention Lab",
    "Research Lab",
    "Cloning Center",
    "Market Hub",
    "Reprocessing Facility",
    "Moon Drill",
    "Reactor",
)

# Short rig labels for the card tags: (words in the rig name, label).
RIG_LABELS = (
    ("Thukker Advanced Component", "Adv. components"),
    ("Thukker Structure and Component", "Components"),
    ("Basic Capital Component", "Capital components"),
    ("Capital Ship Manufacturing", "Capital ship"),
    ("Ship Manufacturing", "Ship"),
    ("Equipment Manufacturing", "Equipment"),
    ("Ammunition Manufacturing", "Ammo"),
    ("Drone and Fighter Manufacturing", "Drones"),
    ("Laboratory Optimization", "Lab"),
    ("Invention", "Invention"),
    ("Reactor Efficiency", "Reactor"),
    ("Biochemical Reactor", "Biochem reactor"),
    ("Composite Reactor", "Composite reactor"),
    ("Hybrid Reactor", "Hybrid reactor"),
    ("Reprocessing Monitor", "Reprocessing"),
    ("Asteroid Ore Grading", "Ore grading"),
    ("Moon Ore Grading", "Moon grading"),
    ("Ice Grading", "Ice grading"),
)

DSCAN_LINE = re.compile(r"^(\d+)\t([^\t]+)\t([^\t]+)(?:\t(.*))?$")
REINFORCE = re.compile(
    r"^(?:reinforces?(?:\s+at)?\s*)?([01]?\d|2[0-3]):([0-5]\d)(?:\s*(?:eve|utc))?$",
    re.IGNORECASE,
)
RIG_SIZE = re.compile(r"\b(M|L|XL)-Set\b")
# Selected Item copies look like "Sosala - WATERMELLON 0 m Reinforced until
# 2024.06.23 23:20:58": drop the distance and the timer.
SELECTED_ITEM_TAIL = re.compile(
    r"\s+[\d.,]+\s*(?:m|km|AU)\b.*$|\s+Reinforced until .*$", re.IGNORECASE
)


@dataclass
class ParsedModule:
    name: str
    slot: str  # rig | service | defense
    size: str = ""
    label: str = ""


@dataclass
class ParsedPaste:
    name: str = ""
    solar_system_name: str = ""
    type_id: Optional[int] = None
    type_name: str = ""
    reinforce_hour: Optional[int] = None
    modules: List[ParsedModule] = field(default_factory=list)
    parts: List[str] = field(default_factory=list)


def classify_module(name: str) -> ParsedModule:
    """Rig, service or defense, with a short tag label for rigs."""
    clean = name.strip()
    size = RIG_SIZE.search(clean)
    if size:
        label = ""
        for words, short in RIG_LABELS:
            if words in clean:
                label = short
                break
        if not label:
            label = re.sub(r"^Standup (M|L|XL)-Set ", "", clean)
            label = re.sub(r"\s+(I|II)$", "", label)
        if label == "Ship":
            label = "Ship ME"
        if clean.endswith(" II") and label in ("Reactor", "Reprocessing"):
            label = f"{label} II"
        return ParsedModule(clean, "rig", size.group(1), label)
    if any(word in clean for word in SERVICE_WORDS):
        label = re.sub(r"^Standup ", "", clean)
        label = re.sub(r"\s+(I|II)$", "", label)
        return ParsedModule(clean, "service", "", label)
    return ParsedModule(clean, "defense", "", "")


def split_structure_name(name: str) -> tuple[str, str]:
    """ "Amamake - Police Weapons Facility" -> ("Amamake", "Police Weapons Facility")."""
    if " - " in name:
        system, rest = name.split(" - ", 1)
        return system.strip(), rest.strip()
    return "", name.strip()


def parse_paste(text: str) -> ParsedPaste:
    """Read whatever a pilot pasted from the EVE client.

    Understands a d-scan line, the Selected Item name, ship scan lines
    (Standup modules) and a reinforce time ("Reinforces 20:00")."""
    result = ParsedPaste()
    seen = set()
    for raw in (text or "").splitlines():
        line = raw.strip().rstrip("…").strip()
        if not line:
            continue
        dscan = DSCAN_LINE.match(raw.strip("\r\n"))
        if dscan:
            result.type_id = int(dscan.group(1))
            result.name = result.name or dscan.group(2).strip()
            result.type_name = dscan.group(3).strip()
            seen.add("dscan")
            continue
        reinforce = REINFORCE.match(line)
        if reinforce:
            result.reinforce_hour = int(reinforce.group(1))
            seen.add("reinforce")
            continue
        # Ship scan rows may carry a slot column; keep the Standup name.
        standup = re.search(r"(Standup [^\t]+)", line)
        if standup:
            result.modules.append(classify_module(standup.group(1)))
            seen.add("fitting")
            continue
        if not result.name:
            result.name = SELECTED_ITEM_TAIL.sub("", line).strip()
            seen.add("name")
    if result.name:
        result.solar_system_name = split_structure_name(result.name)[0]
    result.parts = [
        p for p in ("name", "dscan", "fitting", "reinforce") if p in seen
    ]
    return result


def fitting_summary(modules: Iterable[dict]) -> dict:
    """Counts for "3 rigs, 5 services, 4 defenses"."""
    counts = {"rig": 0, "service": 0, "defense": 0}
    for module in modules:
        slot = module.get("slot")
        if slot in counts:
            counts[slot] += 1
    return counts


def modules_as_json(modules: List[ParsedModule]) -> List[dict]:
    return [
        {"name": m.name, "slot": m.slot, "size": m.size, "label": m.label}
        for m in modules
    ]


# Who can see what ---------------------------------------------------------


def can_manage(user) -> bool:
    return can_use_feature(user, MANAGE_FEATURE)


def can_view_alliance(user) -> bool:
    return can_use_feature(user, VIEW_FEATURE)


def user_tribe_group_ids(user) -> set:
    if user is None or not user.is_authenticated:
        return set()
    # pylint: disable=import-outside-toplevel
    from tribes.models import TribeGroupMembership

    return set(
        TribeGroupMembership.objects.filter(
            user=user, status=TribeGroupMembership.STATUS_ACTIVE
        ).values_list("tribe_group_id", flat=True)
    )


def visible_locations(user):
    """EveLocations this user may see on the structure browser."""
    queryset = EveLocation.objects.all()
    if user is not None and user.is_authenticated and can_manage(user):
        return queryset
    if (
        user is None
        or not user.is_authenticated
        or not can_view_alliance(user)
    ):
        return queryset.filter(audience=EveLocation.AUDIENCE_PUBLIC)
    groups = user_tribe_group_ids(user)
    corporation_ids = set(
        EveCharacter.objects.filter(user=user).values_list(
            "corporation_id", flat=True
        )
    )
    return queryset.filter(
        Q(
            audience__in=[
                EveLocation.AUDIENCE_PUBLIC,
                EveLocation.AUDIENCE_ALLIANCE,
            ]
        )
        | Q(
            audience=EveLocation.AUDIENCE_GROUPS,
            audience_groups__tribe_group_id__in=groups,
        )
        | Q(
            audience=EveLocation.AUDIENCE_GROUPS,
            audience_groups__corporation__corporation_id__in=corporation_ids,
        )
    ).distinct()


def holdings(user, location_ids: Iterable[int]) -> dict:
    """{location_id: {"clones": n, "items": n}} for the user's characters."""
    ids = list(location_ids)
    out = {lid: {"clones": 0, "items": 0} for lid in ids}
    if user is None or not user.is_authenticated or not ids:
        return out
    clones = (
        EveCharacterClone.objects.filter(
            character__user=user, location_id__in=ids
        )
        .values("location_id")
        .annotate(n=Count("id"))
    )
    for row in clones:
        out[row["location_id"]]["clones"] = row["n"]
    items = (
        EveCharacterAsset.objects.filter(
            character__user=user, location_id__in=ids
        )
        .values("location_id")
        .annotate(n=Count("id"))
    )
    for row in items:
        out[row["location_id"]]["items"] = row["n"]
    return out


def open_order_counts(location_ids: Iterable[int]) -> dict:
    # pylint: disable=import-outside-toplevel
    from industry.models import IndustryOrder

    rows = (
        IndustryOrder.objects.filter(
            location_id__in=list(location_ids), fulfilled_at__isnull=True
        )
        .values("location_id")
        .annotate(n=Count("id"))
    )
    return {row["location_id"]: row["n"] for row in rows}


def route_counts(location_ids: Iterable[int]) -> dict:
    # pylint: disable=import-outside-toplevel
    from freight.models import EveFreightRoute

    ids = list(location_ids)
    counts = {lid: 0 for lid in ids}
    for origin, destination in EveFreightRoute.objects.filter(
        active=True
    ).values_list("origin_location_id", "destination_location_id"):
        if origin in counts:
            counts[origin] += 1
        if destination in counts:
            counts[destination] += 1
    return counts


# Finding the structure ID --------------------------------------------------


@dataclass
class Match:
    status: str  # listed | pending | found | none
    location_id: Optional[int] = None
    source: str = ""  # listed | structure | assets | search | docked
    name: str = ""
    solar_system_name: str = ""
    type_id: Optional[int] = None
    found_with: str = ""  # character name for search / docked


def _search_with_characters(user, name: str) -> tuple[Optional[int], str]:
    """ESI structure search with each of the user's characters."""
    for character in EveCharacter.objects.filter(user=user):
        try:
            response = EsiClient(character).search_category("structure", name)
        except Exception:  # pylint: disable=broad-except
            logger.info(
                "Structure search failed for %s", character.character_id
            )
            continue
        if not response.success():
            continue
        ids = (response.data or {}).get("structure") or []
        if len(ids) == 1:
            return int(ids[0]), character.character_name
    return None, ""


def find_structure(user, name: str, type_id: Optional[int] = None) -> Match:
    """Look for the structure's ID: known locations, pending submissions,
    alliance-owned structures, pilots' assets, then ESI structure search."""
    name = (name or "").strip()
    system, _ = split_structure_name(name)
    if not name:
        return Match(status="none")
    listed = EveLocation.objects.filter(location_name__iexact=name).first()
    if listed:
        return Match(
            status="listed",
            location_id=listed.location_id,
            source="listed",
            name=listed.location_name,
            solar_system_name=listed.solar_system_name,
            type_id=listed.type_id or type_id,
        )
    pending = LocationSubmission.objects.filter(
        name__iexact=name, status=LocationSubmission.STATUS_PENDING
    ).first()
    if pending:
        return Match(
            status="pending",
            location_id=pending.location_id,
            source=pending.id_source,
            name=pending.name,
            solar_system_name=pending.solar_system_name,
            type_id=pending.type_id or type_id,
        )
    structure = EveStructure.objects.filter(name__iexact=name).first()
    if structure:
        return Match(
            status="found",
            location_id=structure.id,
            source="structure",
            name=structure.name,
            solar_system_name=structure.system_name,
            type_id=structure.type_id,
        )
    asset = (
        EveCharacterAsset.objects.filter(location_name__iexact=name)
        .exclude(location_id__isnull=True)
        .first()
    )
    if asset:
        return Match(
            status="found",
            location_id=asset.location_id,
            source="assets",
            name=name,
            solar_system_name=system,
            type_id=type_id,
        )
    if user is not None and user.is_authenticated:
        structure_id, character_name = _search_with_characters(user, name)
        if structure_id:
            return Match(
                status="found",
                location_id=structure_id,
                source="search",
                name=name,
                solar_system_name=system,
                type_id=type_id,
                found_with=character_name,
            )
    return Match(
        status="none", name=name, solar_system_name=system, type_id=type_id
    )


def docked_locations(user) -> List[dict]:
    """Where the user's characters are docked right now (ESI location)."""
    out = []
    for character in EveCharacter.objects.filter(user=user):
        try:
            response = EsiClient(character).get_character_location()
        except Exception:  # pylint: disable=broad-except
            continue
        if not response.success() or not isinstance(response.data, dict):
            continue
        location_id = response.data.get("structure_id") or response.data.get(
            "station_id"
        )
        if not location_id:
            continue
        known = EveLocation.objects.filter(location_id=location_id).first()
        asset = (
            EveCharacterAsset.objects.filter(location_id=location_id)
            .exclude(location_name="")
            .first()
        )
        out.append(
            {
                "character_id": character.character_id,
                "character_name": character.character_name,
                "location_id": int(location_id),
                "name": (
                    known.location_name
                    if known
                    else (asset.location_name if asset else "")
                ),
                "listed": known is not None,
            }
        )
    return out


# Approval and history ------------------------------------------------------


def record_change(location, user, kind: str, summary: str, details=None):
    return LocationChange.objects.create(
        location=location,
        user=user,
        kind=kind,
        summary=summary[:255],
        details=details or {},
    )


def _solar_system_id(name: str) -> Optional[int]:
    if not name:
        return None
    # pylint: disable=import-outside-toplevel
    from eveuniverse.models import EveSolarSystem

    system = EveSolarSystem.objects.filter(name__iexact=name).first()
    return system.id if system else None


class ApprovalError(Exception):
    pass


@transaction.atomic
def approve_submission(submission: LocationSubmission, user) -> EveLocation:
    if submission.status != LocationSubmission.STATUS_PENDING:
        raise ApprovalError("This submission was already decided.")
    if not submission.location_id:
        raise ApprovalError(
            "This structure has no ID yet. It can be approved once an "
            "alliance pilot docks there or stores something in it."
        )
    if EveLocation.objects.filter(location_id=submission.location_id).exists():
        raise ApprovalError("This structure is already on the list.")
    system_name = (
        submission.solar_system_name
        or split_structure_name(submission.name)[0]
    )
    system_id = submission.solar_system_id or _solar_system_id(system_name)
    if not system_id:
        raise ApprovalError(f"Unknown solar system for {submission.name}.")
    short = submission.short_name or submission.name[:32]
    now = timezone.now()
    location = EveLocation.objects.create(
        location_id=submission.location_id,
        location_name=submission.name,
        solar_system_id=system_id,
        solar_system_name=system_name,
        short_name=short[:32],
        is_structure=submission.location_id > 2_000_000_000,
        type_id=submission.type_id,
        description=submission.description,
        fitting_text=submission.paste_text if submission.fitting else "",
        fitting=submission.fitting,
        fitting_scanned_at=now if submission.fitting else None,
        reinforce_hour=submission.reinforce_hour,
        audience=submission.audience,
        good_for=submission.good_for,
        added_by=submission.submitted_by,
    )
    if submission.audience == EveLocation.AUDIENCE_GROUPS:
        for group_id in submission.audience_tribe_group_ids:
            LocationAudienceGroup.objects.create(
                location=location, tribe_group_id=group_id
            )
    submission.status = LocationSubmission.STATUS_APPROVED
    submission.decided_by = user
    submission.decided_at = now
    submission.save()
    added = record_change(
        location, submission.submitted_by, "added", "added it"
    )
    LocationChange.objects.filter(pk=added.pk).update(
        created_at=submission.created_at
    )
    if submission.fitting:
        counts = fitting_summary(submission.fitting)
        record_change(
            location,
            submission.submitted_by,
            "fitting",
            "pasted a ship scan",
            {"counts": counts},
        )
    record_change(
        location,
        user,
        "approved",
        "approved it",
        {"location_id": location.location_id},
    )
    return location


def decline_submission(submission: LocationSubmission, user, reason: str = ""):
    if submission.status != LocationSubmission.STATUS_PENDING:
        raise ApprovalError("This submission was already decided.")
    submission.status = LocationSubmission.STATUS_DECLINED
    submission.decided_by = user
    submission.decided_at = timezone.now()
    submission.decline_reason = reason[:255]
    submission.save()


def fitting_diff(old: List[dict], new: List[dict]) -> dict:
    old_names = [m.get("name") for m in old]
    new_names = [m.get("name") for m in new]
    added = [n for n in new_names if n not in old_names]
    removed = [n for n in old_names if n not in new_names]
    return {
        "added": added,
        "removed": removed,
        "kept": len(new_names) - len(added),
    }


def attention_items(locations) -> List[dict]:
    """Things a manager should fix, from real location data."""
    items = []
    by_short = {}
    for location in locations:
        by_short.setdefault(location.short_name.lower(), []).append(location)
    for rows in by_short.values():
        if len(rows) > 1:
            items.append(
                {
                    "kind": "duplicate_short_name",
                    "title": f"{len(rows)} locations are called {rows[0].short_name}",
                    "detail": " and ".join(
                        f'"{row.location_name}" ({row.location_id})'
                        for row in rows
                    ),
                    "location_id": rows[0].location_id,
                }
            )
    routes = route_counts(location.location_id for location in locations)
    for location in locations:
        if routes.get(location.location_id) and not location.freight_active:
            items.append(
                {
                    "kind": "routes_but_freight_off",
                    "title": f"{location.short_name} has freight routes, but Freight is off",
                    "detail": f"{routes[location.location_id]} routes start or end there",
                    "location_id": location.location_id,
                }
            )
        if (
            location.is_structure
            and location.freight_active
            and location.reinforce_hour is None
        ):
            items.append(
                {
                    "kind": "no_reinforce_hour",
                    "title": f"{location.short_name} has no reinforce time",
                    "detail": "Haulers can't be warned about its timers",
                    "location_id": location.location_id,
                }
            )
    return items
