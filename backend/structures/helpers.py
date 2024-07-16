import re
from datetime import datetime
from pydantic import BaseModel


class StructureResponse(BaseModel):
    structure_name: str
    location: str
    timer: datetime


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
    timer_pattern = re.compile(r"Reinforced until (.*)")

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
    timer_pattern = re.compile(r"Reinforced until (.*)")

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
