import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Tuple

from pydantic import BaseModel
from django.db.models import Count, Q

from eveonline.scopes import DIRECTOR_SCOPES
from eveonline.client import EsiClient
from eveonline.models import EveCharacter

from structures.models import EveStructure, EveStructurePing, EveStructureTimer

logger = logging.getLogger(__name__)

# Map EVE structure type_id to EveStructureTimer.type slug (type_choices)
STRUCTURE_TYPE_ID_TO_TIMER_TYPE = {
    35825: "raitaru",
    35826: "astrahus",
    35827: "fortizar",
    35832: "sotiyo",
    35833: "keepstar",
    35834: "azbel",
    35835: "tatara",
    35836: "athanor",
    35840: "ansiblex_jump_gate",
    35841: "orbital_skyhook",
    35842: "metenox_moon_drill",
    # Cyno beacons/jammers and others can be added as needed
}


class StructureResponse(BaseModel):
    structure_name: str
    location: str
    timer: datetime


def get_generic_details(structure_name: str, location: str, timer: datetime):
    return StructureResponse(
        structure_name=structure_name,
        location=location,
        timer=timer,
    )


def get_skyhook_details(selected_item_window: str):
    """
    Orbital Skyhook (KBP7-G III) [Sukanan Inititive]
    0.5 AU
    Reinforced until 2024.07.17 11:10:47


    Parse the following using regex:
    Structure (Location) [Owner]
    distance
    state until datetime
    """
    # regex pattern for structure name, location, and owner
    structure_pattern = re.compile(r"(.*) \((.*)\) \[(.*)\]")
    # get the entire timer out
    timer_pattern = re.compile(r" until (.*)")

    # parse the structure name, location, and owner
    structure_match = structure_pattern.match(selected_item_window)
    structure_name = structure_match.group(1)
    location = structure_match.group(2)

    # parse the timer
    timer_match = timer_pattern.search(selected_item_window)

    return StructureResponse(
        structure_name=structure_name,
        location=location,
        timer=datetime.strptime(timer_match.group(1), "%Y.%m.%d %H:%M:%S"),
    )


def get_structure_details(selected_item_window: str):
    """
    Sosala - WATERMELLON
    0 m
    Reinforced until 2024.06.23 23:20:58

    Parse the following using regex:
    system_name - structure_name
    distance
    state until datetime
    """
    # regex pattern for system name and structure name
    structure_pattern = re.compile(r"(.*) - (.*)")
    # get the entire timer out
    timer_pattern = re.compile(r" until (.*)")

    # parse the structure name, location, and owner
    structure_match = structure_pattern.match(selected_item_window)
    system_name = structure_match.group(1)
    structure_name = structure_match.group(2)

    # parse the timer
    timer_match = timer_pattern.search(selected_item_window)

    return StructureResponse(
        structure_name=structure_name,
        location=system_name,
        timer=datetime.strptime(timer_match.group(1), "%Y.%m.%d %H:%M:%S"),
    )


NOTIFICATION_SCOPE = "esi-characters.read_notifications.v1"


def get_notification_characters(corporation_id: int) -> List[EveCharacter]:
    """Characters with all director scopes (for manual flows)."""
    return (
        EveCharacter.objects.annotate(
            matching_scopes=Count(
                "token__scopes",
                filter=Q(token__scopes__name__in=DIRECTOR_SCOPES),
            )
        )
        .filter(
            matching_scopes=len(DIRECTOR_SCOPES),
        )
        .distinct()
        .filter(
            corporation_id=corporation_id,
        )
    )


def get_characters_with_notification_scope_for_structure_corps():
    """
    Characters in corporations that have structures and whose token has
    esi-characters.read_notifications.v1 (used for structure notification polling).
    """
    # EVE corporation IDs (not Django PKs) for corps that have at least one structure
    corp_ids = EveStructure.objects.values_list(
        "corporation__corporation_id", flat=True
    ).distinct()
    return EveCharacter.objects.filter(
        corporation_id__in=corp_ids,
        token__scopes__name=NOTIFICATION_SCOPE,
    ).distinct()


def parse_esi_time(time) -> datetime:
    if time is None:
        return None
    if isinstance(time, datetime):
        return time
    if time[10] == "T":
        return datetime.strptime(time, "%Y-%m-%dT%H:%M:%S%z")
    else:
        return datetime.strptime(time, "%Y-%m-%d %H:%M:%S%z")


# Windows epoch for EVE notification timestamps (100-nanosecond ticks since this time)
_WINDOWS_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def _parse_windows_filetime(value: int) -> datetime | None:
    """Convert EVE notification timestamp from Windows FileTime (100-ns ticks since 1601-01-01) to UTC datetime."""
    if value is None or value <= 0:
        return None
    # 100-nanosecond ticks -> microseconds (divide by 10)
    try:
        total_microseconds = value // 10
        return _WINDOWS_EPOCH + timedelta(microseconds=total_microseconds)
    except (OSError, ValueError, OverflowError):
        return None


def _parse_timestamp_ms(value: int) -> datetime | None:
    """Convert EVE notification timestamp to timezone-aware datetime. Handles Unix ms and Windows FileTime."""
    if value is None or value <= 0:
        return None
    # EVE often uses Windows FileTime (100-ns since 1601): 17–18 digit values
    if value >= 1e15:
        return _parse_windows_filetime(value)
    # Otherwise treat as Unix time (seconds or ms)
    if value < 1e12:
        value = value * 1000  # assume seconds -> ms
    try:
        dt = datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
        # If Unix interpretation gives far-future year, try Windows FileTime (e.g. 9000000000)
        if dt.year > 2100 and value < 1e15:
            alt = _parse_windows_filetime(value)
            if alt and 2000 <= alt.year <= 2100:
                return alt
        return dt
    except (OSError, ValueError):
        return None


_STRUCTURE_NOTIFICATION_KEYS = (
    ("structureID:", "structure_id"),
    ("solarSystemID:", "solar_system_id"),
    ("solarsystemID:", "solar_system_id"),
    ("planetID:", "planet_id"),
    ("typeID:", "type_id"),
    ("structureTypeID:", "type_id"),
    ("timestamp:", "notification_timestamp_raw"),
    ("vulnerableTime:", "vulnerable_time_raw"),
    ("reinforceExitTime:", "reinforce_exit_raw"),
)


def _parse_structure_notification_lines(text: str) -> dict:
    """Parse key-value lines from notification text. Returns dict of raw values."""
    parsed = {
        "structure_id": -1,
        "solar_system_id": None,
        "planet_id": None,
        "type_id": None,
        "notification_timestamp_raw": None,
        "vulnerable_time_raw": None,
        "reinforce_exit_raw": None,
    }
    try:
        for line in text.splitlines():
            line = line.strip()
            for prefix, key in _STRUCTURE_NOTIFICATION_KEYS:
                if line.startswith(prefix):
                    parsed[key] = int(line.split()[-1])
                    break
    except (ValueError, IndexError) as e:
        logger.warning("Error parsing structure notification, %s", e)
    return parsed


def _resolve_timer_end_from_parsed(parsed: dict) -> datetime | None:
    """Compute timer_end from parsed vulnerableTime/reinforceExitTime and optional timestamp."""
    raw = parsed.get("reinforce_exit_raw") or parsed.get("vulnerable_time_raw")
    if raw is None:
        return None
    timer_end = _parse_timestamp_ms(raw)
    ts_raw = parsed.get("notification_timestamp_raw")
    if ts_raw is not None and 1e9 <= raw <= 1e14:
        base = _parse_windows_filetime(ts_raw)
        if base is not None and (timer_end is None or timer_end.year > 2100):
            timer_end = base + timedelta(milliseconds=raw)
            logger.debug(
                "Interpreted vulnerableTime/reinforceExitTime as ms offset from notification timestamp"
            )
    return timer_end


def parse_structure_notification(text: str):
    """
    Parse ESI notification text. Supports:
    - Structure* types: structureID (with optional YAML anchor)
    - OrbitalAttacked / OrbitalReinforced: solarSystemID, planetID, typeID
      (no structureID); we use a synthetic negative id for deduplication.
    - Timer: vulnerableTime (StructureLost*) or reinforceExitTime (OrbitalReinforced).
      EVE may send these as Windows FileTime (100-ns since 1601) or as ms offset from
      notification timestamp; we parse timestamp from text when needed.
    """
    parsed = _parse_structure_notification_lines(text)
    structure_id = parsed["structure_id"]
    solar_system_id = parsed["solar_system_id"]
    planet_id = parsed["planet_id"]
    type_id = parsed["type_id"]

    timer_end = _resolve_timer_end_from_parsed(parsed)

    if (
        structure_id == -1
        and solar_system_id is not None
        and planet_id is not None
    ):
        type_val = type_id if type_id is not None else 0
        synthetic = (
            solar_system_id * 10**9 + planet_id * 10**6 + type_val
        ) % (2**63 - 1)
        structure_id = -synthetic

    return {
        "data": text[0:200],
        "structure_id": structure_id,
        "timer_end": timer_end,
        "solar_system_id": solar_system_id,
        "type_id": type_id,
    }


REINFORCEMENT_NOTIFICATION_STATE = {
    "StructureLostShields": "armor",
    "StructureLostArmor": "hull",
    "OrbitalReinforced": "armor",
}


def ensure_timer_from_reinforcement_notification(  # noqa: C901
    notification_type: str,
    data: dict,
    corporation_name: str,
    alliance_name: str | None,
    system_name_resolver: Callable[[int], str],
) -> EveStructureTimer | None:
    """
    Create or update EveStructureTimer when we have a reinforcement notification
    with a known timer end. Returns the timer if created/updated, else None.
    """
    timer_end = data.get("timer_end")
    if not timer_end:
        return None
    state = REINFORCEMENT_NOTIFICATION_STATE.get(notification_type)
    if not state:
        return None

    structure_id = data.get("structure_id")
    type_id = data.get("type_id")
    solar_system_id = data.get("solar_system_id")

    timer_type = None
    structure = None
    name = None
    system_name = None

    if structure_id is not None and structure_id > 0:
        structure = EveStructure.objects.filter(id=structure_id).first()
        if structure:
            timer_type = STRUCTURE_TYPE_ID_TO_TIMER_TYPE.get(
                structure.type_id
            ) or STRUCTURE_TYPE_ID_TO_TIMER_TYPE.get(type_id)
            name = structure.name
            system_name = structure.system_name
    if not timer_type and type_id is not None:
        timer_type = STRUCTURE_TYPE_ID_TO_TIMER_TYPE.get(type_id)
    if not timer_type:
        return None

    if not system_name and solar_system_id is not None:
        system_name = system_name_resolver(solar_system_id)
    if not system_name:
        system_name = "Unknown"
    if not name:
        name = (
            f"Structure {structure_id}"
            if structure_id and structure_id > 0
            else "Orbital"
        )

    now = datetime.now(timezone.utc)
    existing = None
    if structure:
        existing = (
            EveStructureTimer.objects.filter(
                structure=structure, state=state, timer__gte=now
            )
            .order_by("timer")
            .first()
        )
    if not existing and structure_id and structure_id < 0:
        existing = (
            EveStructureTimer.objects.filter(
                structure__isnull=True,
                state=state,
                system_name=system_name,
                name=name,
                timer__gte=now,
            )
            .order_by("timer")
            .first()
        )

    if existing:
        existing.timer = timer_end
        existing.name = name
        existing.system_name = system_name
        existing.corporation_name = corporation_name
        existing.alliance_name = alliance_name
        existing.updated_at = now
        existing.save()
        logger.info(
            "Updated EveStructureTimer %s (%s) for %s at %s",
            existing.id,
            state,
            name,
            timer_end,
        )
        return existing

    timer = EveStructureTimer.objects.create(
        name=name,
        state=state,
        type=timer_type,
        timer=timer_end,
        system_name=system_name,
        corporation_name=corporation_name,
        alliance_name=alliance_name,
        structure=structure,
    )
    logger.info(
        "Created EveStructureTimer %s (%s) for %s at %s",
        timer.id,
        state,
        name,
        timer_end,
    )
    return timer


def is_new_event(
    event: EveStructurePing, current_time: datetime | None = None
) -> bool:
    if not current_time:
        current_time = datetime.now(timezone.utc)

    now_delta = current_time - event.event_time
    if now_delta.total_seconds() > 1200:
        # Event is more than 20 minutes old, so not new
        return False

    latest = (
        EveStructurePing.objects.filter(structure_id=event.structure_id)
        .exclude(notification_id=event.notification_id)
        .order_by("-event_time")
        .first()
    )
    if not latest:
        # First event for this structure
        return True

    latest_delta = event.event_time - latest.event_time
    if latest_delta.total_seconds() < 3600:
        # Last event for structure less than an hour ago
        return False

    return True


def _apply_aggressor_simple_key(
    stripped: str,
    out: dict,
    key: str,
    prefix: str,
    allow_if_none: bool = False,
) -> bool:
    """If line starts with prefix, set out[key] and return True. If allow_if_none, only set when out[key] is None."""
    if not stripped.startswith(prefix):
        return False
    if allow_if_none and out.get(key) is not None:
        return True
    try:
        out[key] = int(stripped.split()[-1])
    except (ValueError, IndexError):
        pass
    return True


def _apply_aggressor_line(
    stripped: str,
    out: dict,
    in_corp_link_data: bool,
    last_numeric_in_list: int | None,
) -> Tuple[bool, int | None]:
    """Process one line of notification text; return (in_corp_link_data, last_numeric_in_list)."""
    if _apply_aggressor_simple_key(
        stripped, out, "aggressor_character_id", "aggressorID:"
    ):
        return in_corp_link_data, last_numeric_in_list
    if _apply_aggressor_simple_key(
        stripped, out, "aggressor_corporation_id", "aggressorCorpID:"
    ):
        return in_corp_link_data, last_numeric_in_list
    if _apply_aggressor_simple_key(
        stripped, out, "aggressor_alliance_id", "aggressorAllianceID:"
    ):
        return in_corp_link_data, last_numeric_in_list
    if _apply_aggressor_simple_key(
        stripped, out, "aggressor_character_id", "charID:", allow_if_none=True
    ):
        return in_corp_link_data, last_numeric_in_list
    if _apply_aggressor_simple_key(
        stripped,
        out,
        "aggressor_alliance_id",
        "allianceID:",
        allow_if_none=True,
    ):
        return in_corp_link_data, last_numeric_in_list
    if stripped.startswith("corpLinkData:"):
        return True, None
    if in_corp_link_data:
        return _apply_aggressor_corp_link_line(
            stripped, out, last_numeric_in_list
        )
    return in_corp_link_data, last_numeric_in_list


def _apply_aggressor_corp_link_line(
    stripped: str, out: dict, last_numeric_in_list: int | None
) -> Tuple[bool, int | None]:
    """Process a line inside corpLinkData block. Return (in_block, last_numeric)."""
    if stripped.startswith("-"):
        part = stripped[1:].strip()
        if part.isdigit():
            return True, int(part)
        return True, last_numeric_in_list
    if (
        last_numeric_in_list is not None
        and out["aggressor_corporation_id"] is None
    ):
        out["aggressor_corporation_id"] = last_numeric_in_list
    return False, last_numeric_in_list


def _parse_aggressor_from_notification_text(text: str | None) -> dict:
    """Extract aggressor character/corp/alliance IDs from ESI notification body.
    Supports both Orbital* style (aggressorID, aggressorCorpID, aggressorAllianceID)
    and StructureUnderAttack style (charID, allianceID, corpLinkData with corp ID in list).
    """
    out = {
        "aggressor_character_id": None,
        "aggressor_corporation_id": None,
        "aggressor_alliance_id": None,
    }
    if not text:
        return out
    try:
        in_corp_link_data = False
        last_numeric_in_list = None
        for line in text.splitlines():
            in_corp_link_data, last_numeric_in_list = _apply_aggressor_line(
                line.strip(), out, in_corp_link_data, last_numeric_in_list
            )
        if in_corp_link_data and last_numeric_in_list is not None:
            if out["aggressor_corporation_id"] is None:
                out["aggressor_corporation_id"] = last_numeric_in_list
    except (ValueError, IndexError):
        pass
    return out


def _attacker_line_from_notification_text(text: str | None) -> str:
    """Build a single line 'Character (Corp) [Alliance]' for the attacker from notification text, resolving IDs via ESI. Returns empty string if no aggressor or on resolve failure."""
    agg = _parse_aggressor_from_notification_text(text)
    ids = []
    if agg["aggressor_character_id"]:
        ids.append(agg["aggressor_character_id"])
    if agg["aggressor_corporation_id"]:
        ids.append(agg["aggressor_corporation_id"])
    if agg["aggressor_alliance_id"]:
        ids.append(agg["aggressor_alliance_id"])
    if not ids:
        return ""

    try:
        response = EsiClient(None).resolve_universe_names(ids)
        if not response.success():
            return ""
        resolved = {r["id"]: r["name"] for r in response.results()}
    except Exception:
        logger.debug(
            "Failed to resolve aggressor names for Discord ping", exc_info=True
        )
        return ""

    char_name = resolved.get(agg["aggressor_character_id"] or 0) or "?"
    corp_name = resolved.get(agg["aggressor_corporation_id"] or 0) or "?"
    alliance_name = (
        resolved.get(agg["aggressor_alliance_id"] or 0)
        if agg["aggressor_alliance_id"]
        else None
    )
    if alliance_name:
        return f"{char_name} ({corp_name}) [{alliance_name}]"
    return f"{char_name} ({corp_name})"


def discord_message_for_ping(ping: EveStructurePing) -> str:
    ping_text = "@everyone \n" ":scream: STRUCTURE UNDER ATTACK :scream: \n"

    structure = EveStructure.objects.filter(id=ping.structure_id).first()
    if structure:
        ping_text += (
            f"Structure: {structure.name} ({ping.structure_id}) \n"
            f"Type: {structure.type_name} ({structure.type_id}) \n"
            f"Location: {structure.system_name} \n"
        )
    elif ping.structure_id < 0:
        details = (ping.summary or "—")[:200]
        if len(ping.summary or "") > 200:
            details += "…"
        ping_text += f"Structure: Orbital (e.g. Skyhook) – not in structure list \nDetails: {details} \n"
    else:
        ping_text += f"Structure: {ping.structure_id} (not in database) \n"

    ping_text += (
        f"Event: {ping.notification_type} ({ping.notification_id}) \n"
        f"Time: {ping.event_time} \n"
    )
    # Include attacker (who is shooting) when present in notification text
    attacker_line = _attacker_line_from_notification_text(ping.text)
    if attacker_line:
        ping_text += f"Attacker: {attacker_line} \n"

    return ping_text
