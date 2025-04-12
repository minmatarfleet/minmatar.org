from django.test import Client, SimpleTestCase
from app.test import TestCase

from .combatlog import (
    DamageEvent,
    LogEvent,
    character_name,
    damage_events,
    parse,
    parse_line,
    strip_html,
    total_damage,
    update_location,
    repair_events,
)


class ParseCombatLogTest(SimpleTestCase):
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

    def test_undock_location(self):
        event = parse_line(
            "[ 2024.01.01 09:00:00 ] (None) Undocking from Sys I - Moon 1 - SuperStation to Sys solar system."
        )
        location = update_location(event, "nowhere")
        self.assertEqual("Sys", location)
        self.assertEqual(location, event.location)

    def test_jump_location(self):
        event = parse_line(
            "[ 2024.01.01 09:00:00 ] (None) Jumping from Sys to Anywhere"
        )
        location = update_location(event, "Somewhere")
        self.assertEqual("Anywhere", location)
        self.assertEqual(location, event.location)

    def test_combat_location(self):
        event = parse_line(
            "[ 2024.01.01 09:00:00 ] (combat) 567 to [P-1]Bad Guy - Inferno Rage Compiler Error - Hits"
        )
        location = update_location(event, "Somewhere")
        self.assertEqual("Somewhere", location)
        self.assertEqual(location, event.location)

    def test_character_name(self):
        log = (
            "------------------------------------------------------------\n"
            "Gamelog\n"
            "Listener: EvePlayer 123\n"
            "Session Started: 2024.01.01 09:00:00\n"
            "------------------------------------------------------------\n"
            "[ 2024.01.01 09:00:00 ] (combat) 567 to [P-1]Bad Guy - Inferno Rage Compiler Error - Hits\n"
        )
        events = parse(log)

        self.assertEqual(6, len(events))
        self.assertEqual("EvePlayer 123", character_name(events))


class StripHtmlTest(SimpleTestCase):
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


class DamageParseTest(SimpleTestCase):
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

    def test_parse_cap_xfer_ignored(self):
        logs = "[ 2024.09.07 14:58:50 ] (combat) 567 remote capacitor transmitted to YourFriend"

        events = parse(logs)
        self.assertEqual(1, len(events))

        dmg_events = damage_events(events)
        self.assertEqual(0, len(dmg_events))


class RemoteRepsParseTest(SimpleTestCase):

    def test_parse_armor_rep(self):
        logs = "[ 2024.09.07 14:58:50 ] (combat) 220 remote armor repaired to Big Duck - Tankface - Small Remote Armor Repairer II"

        events = parse(logs)
        rep_events = repair_events(events)

        self.assertEqual(1, len(rep_events))
        event = rep_events[0]
        self.assertEqual(220, event.repaired)
        self.assertEqual("armor", event.rep_type)
        self.assertEqual("Big Duck - Tankface", event.entity)
        self.assertEqual("Small Remote Armor Repairer II", event.module)

    def test_parse_shield_rep(self):
        logs = "[ 2024.09.07 14:58:50 ] (combat) 50 remote shield boosted to Red Muppet - Wolf NANO - Small Remote Shield Booster II"

        events = parse(logs)
        rep_events = repair_events(events)

        self.assertEqual(1, len(rep_events))
        event = rep_events[0]
        self.assertEqual(50, event.repaired)
        self.assertEqual("shield", event.rep_type)
        self.assertEqual("Red Muppet - Wolf NANO", event.entity)
        self.assertEqual("Small Remote Shield Booster II", event.module)

    def test_parse_shield_rep_2(self):
        logs = "[ 2024.12.12 02:57:43 ] (combat) 488 remote shield boosted to Scythe [NANO] [ABC]  [Big Duck] - - Medium S95a Scoped Remote Shield Booster"

        events = parse(logs)
        rep_events = repair_events(events)

        self.assertEqual(1, len(rep_events))
        event = rep_events[0]
        self.assertEqual(488, event.repaired)
        self.assertEqual("shield", event.rep_type)
        self.assertEqual("Scythe [NANO] [ABC]  [Big Duck] -", event.entity)
        self.assertEqual(
            "Medium S95a Scoped Remote Shield Booster", event.module
        )


class CombatLogRouterTest(TestCase):
    """Test the CombatLog API endpoints"""

    def setUp(self):
        self.client = Client()

        super().setUp()

    def test_analyse_log_endpoint(self):
        log = (
            "------------------------------------------------------------\n"
            "Gamelog\n"
            "Listener: EvePlayer 123\n"
            "Session Started: 2024.01.01 09:00:00\n"
            "------------------------------------------------------------\n"
            "[ 2024.01.01 09:00:00 ] (combat) 567 to [P-1]Bad Guy - Inferno Rage Compiler Error - Hits\n"
            "[ 2024.01.01 09:00:10 ] (combat) 456 from [P-1]Bad Guy - Pea Shooter - Hits\n"
        )
        response = self.client.post("/api/combatlog", log, "text/plain")
        self.assertEqual(200, response.status_code)
        analysis = response.json()
        self.assertEqual(7, analysis["logged_events"])
        self.assertEqual(567, analysis["damage_done"])
        self.assertEqual(456, analysis["damage_taken"])

    def test_save_logs(self):
        log = "[ 2024.01.01 09:00:00 ] (combat) 567 to [P-1]Bad Guy - Inferno Rage Compiler Error - Hits\n"
        response = self.client.post(
            "/api/combatlog?store=true",
            log,
            "text/plain",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

        response = self.client.get(
            "/api/combatlog",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        logs = response.json()
        self.assertEqual(1, len(logs))

        log_id = logs[0]["id"]

        response = self.client.get(
            f"/api/combatlog/{log_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

        response = self.client.delete(
            f"/api/combatlog/{log_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
