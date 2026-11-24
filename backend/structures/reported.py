"""Structures pilots report, and how a report finds the row it describes.

A report never knows the structure's ESI id, so it is matched on what a
pilot can see in space: the system, the type and the name. Reported rows
get ids from a far-negative range (EveStructure.REPORTED_ID_BASE) and are
always alliance-wide. When the hourly ESI sync later meets the same
structure, the reported row is folded into the ESI row.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from django.db import IntegrityError, transaction
from django.db.models import Min
from django.utils import timezone

from eveonline.models import EveCorporation
from structures.models import EveStructure, EveStructureTimer

logger = logging.getLogger(__name__)

# Types a pilot can report, by type id.
REPORTABLE_TYPES = {
    35832: "Astrahus",
    35833: "Fortizar",
    35834: "Keepstar",
    35825: "Raitaru",
    35826: "Azbel",
    35827: "Sotiyo",
    35835: "Athanor",
    35836: "Tatara",
    35841: "Ansiblex Jump Gate",
    81826: "Metenox Moon Drill",
}


class ReportError(ValueError):
    pass


def normalise_name(name: str, system_name: str = "") -> str:
    """Lower case, single spaces, without a leading "<system> - "."""
    value = re.sub(r"\s+", " ", (name or "").strip()).lower()
    if system_name:
        prefix = f"{system_name.strip().lower()} - "
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value


def _esi_ids(names: list[str]) -> dict:
    """ESI's exact name lookup, or {} when ESI cannot answer."""
    # pylint: disable=import-outside-toplevel
    from eveonline.client import EsiClient

    names = [name.strip() for name in names if name and name.strip()]
    if not names:
        return {}
    try:
        response = EsiClient(None).resolve_universe_ids(names)
        if not response.success():
            return {}
        return response.results() or {}
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("ESI name lookup failed for %s", names, exc_info=True)
        return {}


def _esi_id(found: dict, key: str, name: str) -> Optional[int]:
    for row in found.get(key) or []:
        if str(row.get("name", "")).lower() == name.strip().lower():
            return int(row["id"])
    return None


def solar_system_id(name: str) -> Optional[int]:
    """
    The system's id. The local universe table only holds the systems
    something has loaded, which leaves out most of null-sec (where jump
    gates are), so an unknown name is looked up in ESI and loaded.
    """
    if not name or not name.strip():
        return None
    # pylint: disable=import-outside-toplevel
    from eveuniverse.models import EveSolarSystem

    system = EveSolarSystem.objects.filter(name__iexact=name.strip()).first()
    if system:
        return system.id
    system_id = _esi_id(_esi_ids([name]), "systems", name)
    if system_id is None:
        return None
    try:
        EveSolarSystem.objects.get_or_create_esi(id=system_id)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Could not load solar system %s", system_id)
    return system_id


def default_name(system_name: str, type_id: int) -> str:
    """The name a report without one gets: "<system> - <type>"."""
    return f"{system_name} - {REPORTABLE_TYPES[type_id]}"


def _has_default_name(structure: EveStructure) -> bool:
    """A reported row still named after its type, so the reporter left
    the name empty and it may hold the wrong type."""
    return (
        structure.source == EveStructure.SOURCE_REPORTED
        and normalise_name(structure.name, structure.system_name)
        == (structure.type_name or "").strip().lower()
    )


def candidates(
    structures: Iterable[EveStructure], type_id: int, name: str, system_name
) -> list[EveStructure]:
    """Rows in the system worth offering: same type, a similar name, or a
    reported row with no name of its own (its type may be the mistake the
    reporter is correcting)."""
    wanted = normalise_name(name, system_name)
    picked = []
    for structure in structures:
        same_type = structure.type_id == type_id
        theirs = normalise_name(structure.name, structure.system_name)
        similar = bool(wanted) and (wanted in theirs or theirs in wanted)
        if same_type or similar or _has_default_name(structure):
            picked.append(structure)
    picked.sort(
        key=lambda s: (
            normalise_name(s.name, s.system_name) != wanted,
            s.type_id != type_id,
            s.name,
        )
    )
    return picked


@dataclass
class Match:
    structure: Optional[EveStructure]
    ambiguous: bool = False


def match_structure(
    structures: Iterable[EveStructure],
    type_id: int,
    name: str,
    system_name: str,
    corporation_name: str = "",
) -> Match:
    """
    The first rule with exactly one hit wins:
    1. the same normalised name;
    2. the same type and owning corporation;
    3. with no name given, the only structure of that type.
    More than one hit on a rule is ambiguous.
    """
    rows = list(structures)
    wanted = normalise_name(name, system_name)
    if wanted:
        named = [
            s for s in rows if normalise_name(s.name, s.system_name) == wanted
        ]
        if len(named) == 1:
            return Match(named[0])
        if len(named) > 1:
            return Match(None, ambiguous=True)
    if corporation_name:
        owned = [
            s
            for s in rows
            if s.type_id == type_id
            and s.owner_name.strip().lower()
            == corporation_name.strip().lower()
        ]
        if len(owned) == 1:
            return Match(owned[0])
        if len(owned) > 1:
            return Match(None, ambiguous=True)
    if not wanted:
        same_type = [s for s in rows if s.type_id == type_id]
        if len(same_type) == 1:
            return Match(same_type[0])
        if len(same_type) > 1:
            return Match(None, ambiguous=True)
    return Match(None)


@dataclass
class ReportDetails:
    system_name: str
    type_id: int
    name: str = ""
    corporation_name: str = ""
    alliance_name: str = ""
    reinforce_hour: Optional[int] = None
    fitting: str = ""


def _clean(details: ReportDetails) -> ReportDetails:
    if details.type_id not in REPORTABLE_TYPES:
        raise ReportError("Pick a structure type from the list.")
    if details.reinforce_hour is not None and not (
        0 <= details.reinforce_hour <= 23
    ):
        raise ReportError("The reinforcement hour is 0 to 23, in EVE time.")
    details.name = re.sub(r"\s+", " ", details.name or "").strip()[:255]
    details.corporation_name = (details.corporation_name or "").strip()[:255]
    details.alliance_name = (details.alliance_name or "").strip()[:255]
    details.fitting = (details.fitting or "").strip()
    if details.corporation_name and not details.alliance_name:
        details.alliance_name = owner_alliance_name(details.corporation_name)
    return details


def _next_reported_id() -> int:
    lowest = EveStructure.all_objects.filter(
        id__lte=EveStructure.REPORTED_ID_BASE
    ).aggregate(lowest=Min("id"))["lowest"]
    return (
        (lowest - 1) if lowest is not None else EveStructure.REPORTED_ID_BASE
    )


def _corporation(name: str) -> Optional[EveCorporation]:
    if not name:
        return None
    return EveCorporation.objects.filter(name__iexact=name).first()


def owner_alliance_name(corporation_name: str) -> str:
    """
    The alliance the owning corporation is in, so a reporter only types the
    corporation from Show Info: from our own records when we know the
    corporation, else from ESI. Empty when it has none or ESI cannot say.
    """
    if not corporation_name:
        return ""
    corporation = _corporation(corporation_name)
    if corporation is not None and corporation.alliance_id:
        return corporation.alliance.name or ""
    # pylint: disable=import-outside-toplevel
    from eveonline.client import EsiClient
    from eveonline.models import EveAlliance

    corporation_id = _esi_id(
        _esi_ids([corporation_name]), "corporations", corporation_name
    )
    if corporation_id is None:
        return ""
    client = EsiClient(None)
    try:
        info = client.get_corporation(corporation_id)
        if not info.success():
            return ""
        alliance_id = (info.results() or {}).get("alliance_id")
        if not alliance_id:
            return ""
        known = EveAlliance.objects.filter(alliance_id=alliance_id).first()
        if known is not None and known.name:
            return known.name
        alliance = client.get_alliance(alliance_id)
        if not alliance.success():
            return ""
        return str((alliance.results() or {}).get("name") or "")
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning(
            "ESI alliance lookup failed for %s",
            corporation_name,
            exc_info=True,
        )
        return ""


def apply_report(structure: EveStructure, details: ReportDetails, user):
    """
    Update a row from a report. On an ESI row a report only fills what ESI
    leaves empty (fitting, reinforcement hour) and never
    touches ESI-owned fields (type included). On a reported row it also
    corrects the type. It never changes visibility or source.
    """
    now = timezone.now()
    if structure.source == EveStructure.SOURCE_ESI:
        if details.fitting and not structure.fitting:
            structure.fitting = details.fitting
        if (
            details.reinforce_hour is not None
            and structure.reinforce_hour is None
        ):
            structure.reinforce_hour = details.reinforce_hour
    else:
        if details.type_id != structure.type_id:
            # A reported row's type is only what a pilot picked, so a
            # later report on the same row corrects it.
            if not details.name and _has_default_name(structure):
                structure.name = default_name(
                    structure.system_name, details.type_id
                )
            structure.type_id = details.type_id
            structure.type_name = REPORTABLE_TYPES[details.type_id]
        if details.name:
            structure.name = details.name
        if details.corporation_name:
            corporation = _corporation(details.corporation_name)
            structure.corporation = corporation
            structure.owner_corporation_name = (
                "" if corporation else details.corporation_name
            )
        if details.alliance_name:
            structure.owner_alliance_name = details.alliance_name
        if details.reinforce_hour is not None:
            structure.reinforce_hour = details.reinforce_hour
        if details.fitting:
            structure.fitting = details.fitting
    structure.last_confirmed_at = now
    structure.last_confirmed_by = user
    structure.save()
    return structure


def create_reported(
    details: ReportDetails, system_id: int, user, possible_duplicate=False
) -> EveStructure:
    corporation = _corporation(details.corporation_name)
    now = timezone.now()
    for _ in range(5):
        try:
            with transaction.atomic():
                return EveStructure.objects.create(
                    id=_next_reported_id(),
                    system_id=system_id,
                    system_name=details.system_name,
                    type_id=details.type_id,
                    type_name=REPORTABLE_TYPES[details.type_id],
                    name=details.name
                    or default_name(details.system_name, details.type_id),
                    reinforce_hour=details.reinforce_hour,
                    fitting=details.fitting or None,
                    corporation=corporation,
                    owner_corporation_name=(
                        "" if corporation else details.corporation_name
                    ),
                    owner_alliance_name=details.alliance_name,
                    visibility=EveStructure.VISIBILITY_ALLIANCE,
                    source=EveStructure.SOURCE_REPORTED,
                    reported_by=user,
                    reported_at=now,
                    last_confirmed_at=now,
                    last_confirmed_by=user,
                    possible_duplicate=possible_duplicate,
                )
        except IntegrityError:
            continue
    raise ReportError("Could not save the report. Try again.")


def record_report(
    user, details: ReportDetails, picked: Optional[EveStructure], visible
) -> EveStructure:
    """
    Store a report. `picked` is the row the reporter chose from the
    structures they can see, or None for "it is new". `visible` is the
    reporter's visible queryset. A new report still checks the rows the
    reporter cannot see, and the answer to the reporter is the same either
    way, so a report never tells them a hidden structure exists.
    """
    details = _clean(details)
    system_id = solar_system_id(details.system_name)
    if system_id is None:
        raise ReportError("We do not know that system. Check its spelling.")
    if picked is not None:
        return apply_report(picked, details, user)

    in_system = EveStructure.objects.filter(system_id=system_id)
    hidden = in_system.exclude(id__in=visible.values("id"))
    match = match_structure(
        hidden,
        details.type_id,
        details.name,
        details.system_name,
        details.corporation_name,
    )
    if match.structure is not None:
        return apply_report(match.structure, details, user)
    return create_reported(
        details, system_id, user, possible_duplicate=match.ambiguous
    )


def absorb_reported_structure(esi_structure: EveStructure) -> int:
    """
    The ESI sync met a structure for the first time. A reported row for it
    hands over its timers and becomes the ESI row's history: the ESI row
    keeps the reporter and alliance-wide visibility, since pilots already
    saw it. Returns how many reported rows were folded in.
    """
    reported = EveStructure.objects.filter(
        source=EveStructure.SOURCE_REPORTED, system_id=esi_structure.system_id
    )
    match = match_structure(
        reported,
        esi_structure.type_id,
        esi_structure.name,
        esi_structure.system_name,
    )
    if match.structure is None:
        return 0
    row = match.structure
    with transaction.atomic():
        EveStructureTimer.objects.filter(structure=row).update(
            structure=esi_structure
        )
        esi_structure.visibility = EveStructure.VISIBILITY_ALLIANCE
        esi_structure.reported_by = row.reported_by
        esi_structure.reported_at = row.reported_at
        esi_structure.last_confirmed_at = row.last_confirmed_at
        esi_structure.last_confirmed_by = row.last_confirmed_by
        if not esi_structure.affiliated_alliance_name:
            esi_structure.affiliated_alliance_name = (
                row.affiliated_alliance_name
            )
        esi_structure.save()
        row.delete()
    logger.info(
        "Folded reported structure %s into ESI structure %s",
        row.id,
        esi_structure.id,
    )
    return 1
