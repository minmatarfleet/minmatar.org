from pathlib import Path

import html

class LogEvent:
    raw_log: str
    event_time: str
    event_type: str
    text: str

class DamageEvent:
    damage: int
    direction: str
    entity: str

class LogAnalysis:
    logged_events: int
    damage_done: int
    damage_taken: int

def parse(text):
    events = []
    for line in text.splitlines():
        line = line.strip()
        
        if line.startswith("["):
            pos = line.find("]")

            event = LogEvent()
            
            event.event_time = line[1:pos-1].strip()
            text = line[pos+1:].strip()

            pos = text.find(")")
            if pos == -1:
                event.event_type = "unknown"
            else:
                event.event_type = text[1:pos].strip()
                text = text[pos+1:]

            event.text = strip_html(text)

            events.append(event)

            #print(event.event_time, "|", event.event_type, "|", event.text)
        else:
            event = LogEvent()
            event.event_time = ""
            event.event_type = "unknown"
            event.text = line
            events.append(event)

    return events

def strip_html(text):
    text = text.strip()
    start = text.find("<")
    while start >= 0:
        end = text.find(">")
        if start > 0:
            text = text[0:start] + text[end+1:]
        else:
            text = text[end+1:]
        start = text.find("<")

    return text

def damage_events(events):
    damage_events = []
    for event in events:
        if event.event_type == "combat":
            damage_event = DamageEvent()
            pos = event.text.find(" to ")
            if pos >= 0:
                damage_event.damage = int(event.text[0:pos])            
                damage_event.direction = "to"
                damage_events.append(damage_event)
            
            pos = event.text.find(" from ")
            if pos >= 0:
                damage_event.damage = int(event.text[0:pos])
                damage_event.direction = "from"
                damage_events.append(damage_event)

    return damage_events

def damage_done(damage_events):
    total_done = 0
    total_taken = 0
    for event in damage_events:
        if event.direction == "to":
            total_done += event.damage

        if event.direction == "from":           
            total_taken += event.damage

            
    return (total_done, total_taken)

if __name__ == "__main__":
    combat_log_content = Path("./testlog1.txt").read_text()
    events = parse(combat_log_content)

    analysis = LogAnalysis()
    analysis.logged_events = len(events)

    damage_events = damage_events(events)    

    (analysis.total_done, analysis.damage_taken) = damage_done(damage_events)
    print("Damage done = ", analysis.total_done)
    print("Damage taken = ", analysis.damage_taken)
