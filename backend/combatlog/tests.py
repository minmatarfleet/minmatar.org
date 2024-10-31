from django.test import TestCase

from .combatlog import (
    DamageEvent,
    LogEvent,
    damage_events,
    enemy_damage,
    parse,
    parse_line,
    strip_html,
    total_damage,
)


class ParseCombatLogTest(TestCase):
    def test_parse_line_combat(self):
        log_line = "[ 2024.09.07 14:58:50 ] (combat) <color=0xff00ffff><b>567</b> <color=0x77ffffff><font size=10>to</font> <b><color=0xffffffff>Angel Cartel Codebug</b><font size=10><color=0x77ffffff> - Inferno Rage Compiler Error - Hits"
        event = parse_line(log_line)
        self.assertEqual(event.event_time, "2024.09.07 14:58:50")
        self.assertEqual(event.event_type, "combat")
        self.assertEqual(
            event.text,
            "567 to Angel Cartel Codebug - Inferno Rage Compiler Error - Hits",
        )

    def test_parse_line_hint(self):
        log_line = (
            "[ 2024.09.07 13:59:17 ] (hint) Attempting to join a channel"
        )
        event = parse_line(log_line)
        self.assertEqual(event.event_time, "2024.09.07 13:59:17")
        self.assertEqual(event.event_type, "hint")
        self.assertEqual(event.text, "Attempting to join a channel")

    def test_parse_line_session(self):
        log_line = "  Session Started: 2024.09.07 13:59:16"
        event = parse_line(log_line)
        self.assertEqual(event.event_time, "")
        self.assertEqual(event.event_type, "unknown")
        self.assertEqual(event.text, "Session Started: 2024.09.07 13:59:16")

    def test_parse_logs(self):
        logs = "ABC\nXYZ"
        events = parse(logs)
        self.assertEqual(2, len(events))

    def test_parse_empty_logs(self):
        logs = ""
        events = parse(logs)
        self.assertEqual(0, len(events))


class StripHtmlTest(TestCase):
    def test_strip_html_basic(self):
        stripped = strip_html("hello <b>world</b>")
        self.assertEqual("hello world", stripped)

    def test_strip_html_no_tags(self):
        stripped = strip_html("hello world")
        self.assertEqual("hello world", stripped)

    def test_strip_html_empty(self):
        stripped = strip_html("")
        self.assertEqual("", stripped)


def log_event(event_time, event_type, event_text):
    event = LogEvent()
    event.event_time = event_time
    event.event_type = event_type
    event.text = event_text
    return event


def damage_event(
    damage: int, direction: str, entity: str, weapon: str, outcome: str
) -> DamageEvent:
    event = DamageEvent()
    event.damage = damage
    event.direction = direction
    event.entity = entity
    event.weapon = weapon
    event.outcome = outcome
    return event


class DamageParseTest(TestCase):
    def test_find_damage_events(self):
        events = []
        events.append(log_event("", "combat", "123 from Rat"))
        events.append(log_event("", "combat", "345 to Rat"))
        events.append(log_event("", "peace", "collaborating"))

        dmg_events = damage_events(events)

        self.assertEqual(2, len(dmg_events))

    def test_total_damage_done(self):
        events = []
        events.append(log_event("", "combat", "120 to Rat"))
        events.append(log_event("", "combat", "140 to Rat"))
        events.append(log_event("", "combat", "125 from Rat"))
        events.append(log_event("", "combat", "155 from Rat"))

        dmg_events = damage_events(events)

        self.assertEqual(4, len(dmg_events))

        (dmg_done, dmg_taken) = total_damage(dmg_events)

        self.assertEqual(260, dmg_done)
        self.assertEqual(280, dmg_taken)

    def test_damage_parse(self):
        events = []
        events.append(
            log_event("", "combat", "120 from Rat - Sharp Teeth - Hits")
        )

        dmg_events = damage_events(events)

        self.assertEqual(120, dmg_events[0].damage)
        self.assertEqual("from", dmg_events[0].direction)
        self.assertEqual("Rat", dmg_events[0].entity)
        self.assertEqual("Sharp Teeth", dmg_events[0].weapon)
        self.assertEqual("Hits", dmg_events[0].outcome)

    def test_enemy_damage(self):
        events = []
        events.append(damage_event(100, "from", "Rat", "Sharp Teeth", "Hits"))
        events.append(damage_event(123, "from", "Bat", "Sharp Teeth", "Hits"))
        events.append(damage_event(110, "from", "Rat", "Sharp Teeth", "Hits"))
        events.append(damage_event(125, "to", "Rat", "Sharp Teeth", "Hits"))

        enemies = enemy_damage(events, "from")

        self.assertEqual(210, enemies["Rat"])
        self.assertEqual(123, enemies["Bat"])

        enemies = enemy_damage(events, "to")

        self.assertEqual(125, enemies["Rat"])

    def test_parse_hyphen_names(self):
        """Verify that log entries with hyphens in names work OK"""

        logs = "[ 2024.09.07 14:58:50 ] (combat) 567 to [P-1]Bad Guy - Inferno Rage Compiler Error - Hits"

        events = parse(logs)
        dmg_events = damage_events(events)
        self.assertEqual(1, len(dmg_events))

        event = dmg_events[0]

        self.assertEqual(567, event.damage)
        self.assertEqual("to", event.direction)
        self.assertEqual("Inferno Rage Compiler Error", event.weapon)
        self.assertEqual("[P-1]Bad Guy", event.entity)
