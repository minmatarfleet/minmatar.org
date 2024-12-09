from typing import Dict, List

from pydantic import BaseModel


class LogEvent(BaseModel):
    raw_log: str = None
    event_time: str = None
    event_type: str = None
    location: str = None
    text: str = None


class DamageEvent(BaseModel):
    event_time: str = ""
    damage: int = 0
    direction: str = ""
    entity: str = ""
    weapon: str = ""
    outcome: str = ""
    location: str = ""
    text: str = ""


class DamageAnalysis(BaseModel):
    """Analysis of damage to/from something"""

    name: str
    category: str
    volleys_from: int = 0
    damage_from: int = 0
    max_from: int = 0
    avg_from: int = 0
    volleys_to: int = 0
    damage_to: int = 0
    max_to: int = 0
    avg_to: int = 0
    first: str = ""
    last: str = ""
    location: str = ""


class LogAnalysis(BaseModel):
    """Combat log analysis summary"""

    logged_events: int = 0
    damage_done: int = 0
    damage_taken: int = 0
    weapons: List[DamageAnalysis] = []
    enemies: List[DamageAnalysis] = []
    times: List[DamageAnalysis] = []
    start: str = ""
    end: str = ""
    db_id: int = None
    user_id: int = None
    fitting_id: int = None
    fleet_id: int = None
    character_name: str = None
    final_system: str = None
    max_from: DamageEvent = None
    max_to: DamageEvent = None


def parse_line(line: str) -> LogEvent:
    line = line.strip()

    if line.startswith("["):
        pos = line.find("]")

        event = LogEvent()

        event.event_time = line[1 : pos - 1].strip()
        text = line[pos + 1 :].strip()

        pos = text.find(")")
        if pos == -1:
            event.event_type = "unknown"
        else:
            event.event_type = text[1:pos].strip()
            text = text[pos + 1 :]

        event.text = strip_html(text)
    else:
        event = LogEvent()
        event.event_time = ""
        event.event_type = "unknown"
        event.text = line

    return event


def update_location(event: LogEvent, previous_location: str) -> str:
    if event.text.find("Jumping from ") >= 0:
        split = event.text.find(" to ")
        event.location = event.text[split + 4 :]
    elif event.text.find("Undocking from ") >= 0:
        split = event.text.find(" to ")
        event.location = event.text[split + 4 :].replace(" solar system.", "")
    else:
        event.location = previous_location
    return event.location


def parse(text: str) -> List[LogEvent]:
    location = "{unknown}"
    events = []
    for line in text.splitlines():
        event = parse_line(line)
        location = update_location(event, location)
        events.append(event)

    return events


def character_name(events: List[LogEvent]) -> str:
    for event in events:
        split = event.text.find("Listener: ")
        if split >= 0:
            return event.text[split + 10 :]
    return ""


def strip_html(text):
    text = text.strip()
    start = text.find("<")
    while start >= 0:
        end = text.find(">")
        if start > 0:
            text = text[0:start] + text[end + 1 :]
        else:
            text = text[end + 1 :]
        start = text.find("<")

    return text


def damage_events(events: List[LogEvent]) -> List[DamageEvent]:
    dmg_events = []
    for event in events:
        if event.event_type != "combat":
            continue

        text = event.text

        if len(text) == 0:
            continue

        if text[0] < "0" or text[0] > "9":
            continue

        if text.find("remote armor repaired") >= 0:
            continue

        damage_event = DamageEvent()
        damage_event.event_time = event.event_time
        damage_event.location = event.location

        pos = text.find(" to ")
        if pos >= 0:
            damage_event.damage = int(text[0:pos])
            damage_event.direction = "to"
            text = text[pos + 4 :]

        pos = text.find(" from ")
        if pos >= 0:
            damage_event.damage = int(text[0:pos])
            damage_event.direction = "from"
            text = text[pos + 6 :]

        parts = text.split(" - ")
        if len(parts) >= 1:
            damage_event.entity = parts[0].strip()
        if len(parts) >= 3:
            damage_event.weapon = parts[1].strip()
            damage_event.outcome = parts[2].strip()
        elif len(parts) == 2:
            damage_event.weapon = ""
            damage_event.outcome = parts[1].strip()

        if damage_event.damage > 0:
            damage_event.text = text
            dmg_events.append(damage_event)

    return dmg_events


def total_damage(dmg_events):
    total_done = 0
    total_taken = 0
    for event in dmg_events:
        if event.direction == "to":
            total_done += event.damage

        if event.direction == "from":
            total_taken += event.damage

    return (total_done, total_taken)


def enemy_analysis(dmg_events: List[DamageEvent]) -> List[DamageAnalysis]:
    enemies: Dict[str, DamageAnalysis] = {}

    for event in dmg_events:
        if event.entity not in enemies:
            enemies[event.entity] = DamageAnalysis(
                category="Enemy",
                name=event.entity,
                first=event.event_time,
                last=event.event_time,
            )

        update_damage_analysis(enemies[event.entity], event)

    results = []
    for _, value in enemies.items():
        results.append(value)

    return results


def weapon_analysis(dmg_events: List[DamageEvent]) -> List[DamageAnalysis]:
    weapons: Dict[str, DamageAnalysis] = {}

    for event in dmg_events:
        if event.weapon == "":
            continue

        if event.weapon not in weapons:
            weapons[event.weapon] = DamageAnalysis(
                category="Weapon",
                name=event.weapon,
                first=event.event_time,
                last=event.event_time,
            )

        update_damage_analysis(weapons[event.weapon], event)

    results = []
    for _, value in weapons.items():
        results.append(value)

    return results


def time_analysis(dmg_events: List[DamageEvent]) -> List[DamageAnalysis]:
    times: Dict[str, DamageAnalysis] = {}

    for event in dmg_events:
        time_bucket = event.event_time[0:-1] + "0"

        if time_bucket not in times:
            times[time_bucket] = DamageAnalysis(
                category="TimeBucket",
                name=time_bucket,
                first=event.event_time,
                last=event.event_time,
            )

        update_damage_analysis(times[time_bucket], event)

        if event.location != "":
            times[time_bucket].location = event.location

    results = []
    for _, value in times.items():
        results.append(value)

    return results


def update_damage_analysis(analysis: DamageAnalysis, event: DamageEvent):
    if event.direction == "to":
        analysis.volleys_to += 1
        analysis.damage_to += event.damage
        analysis.max_to = max(analysis.max_to, event.damage)
        analysis.avg_to = round(analysis.damage_to / analysis.volleys_to)

    if event.direction == "from":
        analysis.volleys_from += 1
        analysis.damage_from += event.damage
        analysis.max_from = max(analysis.max_from, event.damage)
        analysis.avg_from = round(analysis.damage_from / analysis.volleys_from)

    analysis.first = min(analysis.first, event.event_time)
    analysis.last = max(analysis.last, event.event_time)


def update_combat_time(events: List[DamageEvent], analysis: LogAnalysis):
    analysis.start = events[0].event_time
    analysis.end = analysis.start
    for event in events:
        analysis.start = min(analysis.start, event.event_time)
        analysis.end = max(analysis.end, event.event_time)


def max_damage(events: List[DamageEvent], direction: str) -> DamageEvent:
    max_dmg = -1
    max_event = None
    for event in events:
        if event.direction == direction and event.damage > max_dmg:
            max_event = event
            max_dmg = event.damage
    return max_event


def final_system_name(events: List[LogEvent]) -> str:
    system = ""
    for event in events:
        if event.location:
            system = event.location
    return system
