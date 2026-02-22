import unittest
from unittest.mock import patch
import factory
from datetime import datetime, timezone

from django.db.models import signals

from esi.models import Token, Scope
from eveonline.client import EsiResponse
from eveonline.models import EveCorporation, EveCharacter
from eveonline.scopes import DIRECTOR_SCOPES
from structures.models import EveStructure, EveStructurePing
from structures.helpers import (
    get_skyhook_details,
    get_structure_details,
    get_notification_characters,
    parse_structure_notification,
    is_new_event,
    discord_message_for_ping,
    parse_esi_time,
    StructureResponse,
    _parse_aggressor_from_notification_text,
)


def make_character(char_id, corp, scopes) -> EveCharacter:
    char = EveCharacter.objects.create(
        character_id=char_id,
        character_name=f"Pilot {char_id}",
        corporation_id=corp.corporation_id if corp else None,
        token=Token.objects.create(
            character_id=char_id,
        ),
    )
    for scope_name in scopes:
        char.token.scopes.add(
            Scope.objects.get_or_create(
                name=scope_name,
            )[0]
        )
    char.token.save()
    return char


class StructureHelperTest(unittest.TestCase):

    def test_get_skyhook_details(self):
        selected_item_window = "Orbital Skyhook (KBP7-G III) [Sukanan Inititive]\n0.5 AU\nReinforced until 2024.07.17 11:10:47"
        expected = StructureResponse(
            structure_name="Orbital Skyhook",
            location="KBP7-G III",
            # "owner": "Sukanan Inititive",
            timer=datetime.strptime(
                "2024.07.17 11:10:47", "%Y.%m.%d %H:%M:%S"
            ),
        )
        self.assertEqual(get_skyhook_details(selected_item_window), expected)

    def test_get_structure_details(self):
        selected_item_window = (
            "Sosala - WATERMELLON\n0 m\nReinforced until 2024.06.23 23:20:58"
        )
        expected = StructureResponse(
            location="Sosala",
            structure_name="WATERMELLON",
            timer=datetime.strptime(
                "2024.06.23 23:20:58", "%Y.%m.%d %H:%M:%S"
            ),
        )
        self.assertEqual(get_structure_details(selected_item_window), expected)

    def test_anchoring_structure(self):
        selected_item_window = (
            "Sosala - WATERMELLON\n0 m\nAnchoring until 2024.06.23 23:20:58"
        )
        expected = StructureResponse(
            location="Sosala",
            structure_name="WATERMELLON",
            timer=datetime.strptime(
                "2024.06.23 23:20:58", "%Y.%m.%d %H:%M:%S"
            ),
        )
        self.assertEqual(get_structure_details(selected_item_window), expected)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_get_notification_characters(self):
        corp = EveCorporation.objects.create(
            corporation_id=1001,
            name="MegaCorp",
        )
        # Helper returns characters that have all DIRECTOR_SCOPES and this corp
        make_character(2001, corp, list(DIRECTOR_SCOPES))
        make_character(2002, corp, [])  # no scopes
        make_character(2003, corp, list(DIRECTOR_SCOPES))
        make_character(2004, corp, list(DIRECTOR_SCOPES))
        make_character(2005, None, list(DIRECTOR_SCOPES))  # wrong corp

        chars = get_notification_characters(corp.corporation_id)

        self.assertEqual(3, chars.count())

    def test_parse_notification(self):
        text = """
            solarsystemID: 30002538
            structureID: &id001 1049253339308
            structureShowInfoData:
             - showinfo
             - 35826
             - *id001
            structureTypeID: 35826
            timeLeft: 1670149438753
            timestamp: 133926971500000000
            vulnerableTime: 9000000000
        """

        data = parse_structure_notification(text)
        self.assertEqual(1049253339308, data["structure_id"])

    def test_parse_orbital_notification(self):
        # OrbitalAttacked / OrbitalReinforced have no structureID; use solarSystemID, planetID, typeID
        text = """
            aggressorAllianceID: 99001234
            aggressorCorpID: 98001234
            aggressorID: 12345678
            planetID: 40234567
            planetTypeID: 13
            shieldLevel: 0.95
            solarSystemID: 30001234
            typeID: 35841
        """
        data = parse_structure_notification(text)
        self.assertLess(data["structure_id"], 0)
        # Same inputs => same synthetic id
        data2 = parse_structure_notification(text)
        self.assertEqual(data["structure_id"], data2["structure_id"])

    def test_parse_aggressor_from_notification_text(self):
        text = """
            aggressorAllianceID: 99001234
            aggressorCorpID: 98001234
            aggressorID: 12345678
        """
        agg = _parse_aggressor_from_notification_text(text)
        self.assertEqual(agg["aggressor_character_id"], 12345678)
        self.assertEqual(agg["aggressor_corporation_id"], 98001234)
        self.assertEqual(agg["aggressor_alliance_id"], 99001234)
        self.assertIsNone(
            _parse_aggressor_from_notification_text(None)[
                "aggressor_character_id"
            ]
        )

    def test_parse_aggressor_structure_under_attack_format(self):
        # StructureUnderAttack uses charID, allianceID, corpLinkData (list with corp ID)
        text = """
            allianceID: 99006225
            allianceName: Rote Works
            charID: 95288372
            corpLinkData:
            - showinfo
            - 2
            - 98602531
            corpName: Navajazos expres Inc.
        """
        agg = _parse_aggressor_from_notification_text(text)
        self.assertEqual(agg["aggressor_character_id"], 95288372)
        self.assertEqual(agg["aggressor_corporation_id"], 98602531)
        self.assertEqual(agg["aggressor_alliance_id"], 99006225)

    def test_parse_notification_includes_timer_end(self):
        # vulnerableTime (Unix ms) is parsed for reinforcement timers
        text = """
            solarsystemID: 30002538
            structureID: 1049253339308
            structureTypeID: 35826
            vulnerableTime: 1730000000000
        """
        data = parse_structure_notification(text)
        self.assertEqual(data["structure_id"], 1049253339308)
        self.assertIsNotNone(data["timer_end"])
        self.assertEqual(data["type_id"], 35826)
        self.assertEqual(data["solar_system_id"], 30002538)

    def test_parse_notification_timer_windows_filetime_offset(self):
        # Real payload: timestamp is Windows FileTime; vulnerableTime can be ms offset from it
        text = """
            solarsystemID: 30002538
            structureID: 1049253339308
            structureTypeID: 35826
            timestamp: 134161908140000000
            vulnerableTime: 9000000000
        """
        data = parse_structure_notification(text)
        self.assertEqual(data["structure_id"], 1049253339308)
        self.assertIsNotNone(data["timer_end"])
        # 9000000000 ms = 104 days after notification time (Windows file time ~2026)
        self.assertGreater(data["timer_end"].year, 2024)
        self.assertLess(data["timer_end"].year, 2030)

    def test_should_ping(self):
        event = EveStructurePing.objects.create(
            notification_id=10000,
            notification_type="Test",
            summary="ABC",
            event_time=datetime(2025, 1, 1, 21, 30, 0, 0, tzinfo=timezone.utc),
        )
        now = datetime(2025, 1, 1, 23, 50, 0, 0, tzinfo=timezone.utc)

        self.assertFalse(is_new_event(event, now))

        now = datetime(2025, 1, 1, 21, 30, 0, 0, tzinfo=timezone.utc)

        self.assertTrue(is_new_event(event, now))

        EveStructurePing.objects.create(
            notification_id=10001,
            notification_type="Test",
            summary="ABC",
            event_time=datetime(2025, 1, 1, 21, 15, 0, 0, tzinfo=timezone.utc),
        )

        self.assertFalse(is_new_event(event, now))

    def test_structure_ping_discord_message(self):
        structure = EveStructure.objects.create(
            id=20001,
            name="Homebase",
            system_id=1,
            system_name="Jita",
            type_id=1234,
            type_name="Bouncy Castle",
            reinforce_hour=12,
            corporation_id=1,
        )
        ping = EveStructurePing.objects.create(
            notification_id=10001,
            notification_type="StructureIsSad",
            structure_id=structure.id,
            summary="ABC",
            event_time=datetime(2025, 1, 1, 21, 15, 0, 0, tzinfo=timezone.utc),
        )
        message = discord_message_for_ping(ping)

        self.assertIn("STRUCTURE UNDER ATTACK", message)
        self.assertIn("Homebase", message)
        self.assertIn("20001", message)
        self.assertIn("Jita", message)
        self.assertIn("Bouncy Castle", message)
        self.assertIn("StructureIsSad", message)

        ping.structure_id = 98765
        ping.save()

        message = discord_message_for_ping(ping)

        self.assertIn("STRUCTURE UNDER ATTACK", message)
        self.assertIn("98765", message)
        self.assertIn("not in database", message)
        self.assertNotIn("Jita", message)

        ping.structure_id = -123456789
        ping.save()
        message = discord_message_for_ping(ping)
        self.assertIn("Orbital", message)
        self.assertIn("Skyhook", message)

    @patch("structures.helpers.EsiClient")
    def test_discord_message_includes_attacker_when_in_notification(
        self, esi_client_mock
    ):
        ping = EveStructurePing(
            notification_id=10002,
            notification_type="StructureUnderAttack",
            structure_id=-999,
            summary="Orbital",
            event_time=datetime(2025, 1, 1, 21, 15, 0, 0, tzinfo=timezone.utc),
            text=(
                "aggressorID: 12345678\n"
                "aggressorCorpID: 98001234\n"
                "aggressorAllianceID: 99001234\n"
            ),
        )
        esi_client_mock.return_value.resolve_universe_names.return_value = (
            EsiResponse(
                0,
                data=[
                    {
                        "id": 12345678,
                        "name": "Bad Guy",
                        "category": "character",
                    },
                    {
                        "id": 98001234,
                        "name": "Evil Corp",
                        "category": "corporation",
                    },
                    {
                        "id": 99001234,
                        "name": "Evil Alliance",
                        "category": "alliance",
                    },
                ],
            )
        )
        message = discord_message_for_ping(ping)
        self.assertIn("Attacker:", message)
        self.assertIn("Bad Guy", message)
        self.assertIn("Evil Corp", message)
        self.assertIn("Evil Alliance", message)

    def assertIsDateTime(self, value):
        self.assertIsInstance(value, datetime)

    def test_parse_esi_time(self):
        self.assertIsNone(parse_esi_time(None))
        self.assertIsDateTime(parse_esi_time(datetime.now()))
        self.assertIsDateTime(parse_esi_time("2025-05-28T23:36:00Z"))
        self.assertIsDateTime(parse_esi_time("2025-05-28T23:36:00+0000"))
        self.assertIsDateTime(parse_esi_time("2025-05-28 23:36:00Z"))
        self.assertIsDateTime(parse_esi_time("2025-05-28 23:36:00+0000"))
