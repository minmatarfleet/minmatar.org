import re
import logging
from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel
from django.db.models import Count, Q

from eveonline.scopes import DIRECTOR_ADDITIONAL_SCOPES
from eveonline.models import EveCharacter

from structures.models import EveStructurePing

logger = logging.getLogger(__name__)


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


def get_notification_characters(corporation_id: int) -> List[EveCharacter]:
    return (
        EveCharacter.objects.annotate(
            matching_scopes=Count(
                "token__scopes",
                filter=Q(token__scopes__name__in=DIRECTOR_ADDITIONAL_SCOPES),
            )
        )
        .filter(
            matching_scopes=len(DIRECTOR_ADDITIONAL_SCOPES),
        )
        .distinct()
        .filter(
            corporation_id=corporation_id,
        )
    )


def parse_structure_notification(text: str):
    structure_id = -1

    try:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("structureID:"):
                id_str = line.split(" ")[-1]
                structure_id = int(id_str)
    except Exception as e:
        logger.warning("Error parsing structure notification, %s", e)

    return {
        "data": text[0:200],
        "structure_id": structure_id,
    }


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
