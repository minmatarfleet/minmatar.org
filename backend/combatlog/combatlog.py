from typing import Dict, List

from pydantic import BaseModel


class LogEvent:
    raw_log: str
    event_time: str
    event_type: str
    text: str


class DamageEvent:
    event_time: str
    damage: int = 0
    direction: str
    entity: str
    weapon: str
    outcome: str
    text: str


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


def parse(text: str) -> List[LogEvent]:
    events = []
    for line in text.splitlines():
        event = parse_line(line)
        events.append(event)

    return events


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

        damage_event = DamageEvent()
        damage_event.event_time = event.event_time

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
