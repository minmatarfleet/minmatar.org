from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase
from discord.models import DiscordChannel, DiscordGuild
from eveuniverse.models import (
    EveCategory,
    EveConstellation,
    EveGroup,
    EveRegion,
    EveSolarSystem,
    EveType,
)

from feed.constants import AMAMAKE_SOLAR_SYSTEM_ID
from feed.helpers.capital_pings import (
    build_capital_ping_payload,
    maybe_notify_capital_kill,
    send_capital_ping_discord,
)
from feed.helpers.capital_ships import (
    is_capital_ship_type,
    killmail_involves_capital,
)
from feed.helpers.system_distance import light_years_between_systems
from feed.models import FeedCapitalPing
from feed.tests.helpers import make_killmail_payload


def make_test_solar_system(
    *,
    solar_system_id: int,
    name: str,
    position_x: float,
    position_y: float,
    position_z: float,
    security_status: float = -0.5,
) -> EveSolarSystem:
    region, _ = EveRegion.objects.get_or_create(
        id=10000030,
        defaults={"name": "Heimatar"},
    )
    constellation, _ = EveConstellation.objects.get_or_create(
        id=20000334,
        defaults={
            "name": "Anher",
            "eve_region": region,
            "position_x": 0.0,
            "position_y": 0.0,
            "position_z": 0.0,
        },
    )
    return EveSolarSystem.objects.create(
        id=solar_system_id,
        name=name,
        eve_constellation=constellation,
        security_status=security_status,
        position_x=position_x,
        position_y=position_y,
        position_z=position_z,
        enabled_sections=0,
    )


def make_capital_ping_channel(*, channel_id: int = 555001) -> DiscordChannel:
    guild, _ = DiscordGuild.objects.get_or_create(
        guild_id=999888777,
        defaults={"name": "Test Guild", "is_active": True},
    )
    return DiscordChannel.objects.create(
        channel_id=channel_id,
        guild=guild,
        name="capital-pings",
        channel_type=DiscordChannel.TEXT,
        receive_capital_pings=True,
    )


class CapitalShipTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ship_category, _ = EveCategory.objects.get_or_create(
            id=6,
            defaults={"name": "Ship", "published": True},
        )
        dread_group, _ = EveGroup.objects.get_or_create(
            id=485,
            defaults={
                "name": "Dreadnought",
                "published": True,
                "eve_category": ship_category,
            },
        )
        battleship_group, _ = EveGroup.objects.get_or_create(
            id=27,
            defaults={
                "name": "Battleship",
                "published": True,
                "eve_category": ship_category,
            },
        )
        EveType.objects.get_or_create(
            id=73790,
            defaults={
                "name": "Revelation Navy Issue",
                "published": True,
                "eve_group": dread_group,
            },
        )
        EveType.objects.get_or_create(
            id=17726,
            defaults={
                "name": "Machariel",
                "published": True,
                "eve_group": battleship_group,
            },
        )

    def test_is_capital_ship_type(self):
        self.assertTrue(is_capital_ship_type(73790))
        self.assertFalse(is_capital_ship_type(17726))

    def test_killmail_involves_capital_from_attacker(self):
        payload = make_killmail_payload(
            136500010,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=17726,
            attacker_ship_type_id=73790,
            attacker_count=3,
        )
        self.assertTrue(killmail_involves_capital(payload["killmail"]))


class SystemDistanceTestCase(TestCase):
    def test_same_system_distance_is_zero(self):
        make_test_solar_system(
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            name="Amamake",
            position_x=0.0,
            position_y=0.0,
            position_z=0.0,
        )
        distance = light_years_between_systems(
            AMAMAKE_SOLAR_SYSTEM_ID,
            AMAMAKE_SOLAR_SYSTEM_ID,
        )
        self.assertEqual(distance, 0.0)

    def test_known_pair_distance(self):
        make_test_solar_system(
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            name="Amamake",
            position_x=-1.24292266288e17,
            position_y=4.41943641937e16,
            position_z=6110392433590000.0,
        )
        make_test_solar_system(
            solar_system_id=30002538,
            name="Vard",
            position_x=-1.283614459209529e17,
            position_y=3.733760356185114e16,
            position_z=5422561601291449.0,
        )
        distance = light_years_between_systems(
            AMAMAKE_SOLAR_SYSTEM_ID,
            30002538,
        )
        self.assertAlmostEqual(distance, 0.8, places=1)


class CapitalPingTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ship_category, _ = EveCategory.objects.get_or_create(
            id=6,
            defaults={"name": "Ship", "published": True},
        )
        dread_group, _ = EveGroup.objects.get_or_create(
            id=485,
            defaults={
                "name": "Dreadnought",
                "published": True,
                "eve_category": ship_category,
            },
        )
        battleship_group, _ = EveGroup.objects.get_or_create(
            id=27,
            defaults={
                "name": "Battleship",
                "published": True,
                "eve_category": ship_category,
            },
        )
        EveType.objects.get_or_create(
            id=73790,
            defaults={
                "name": "Revelation Navy Issue",
                "published": True,
                "eve_group": dread_group,
            },
        )
        EveType.objects.get_or_create(
            id=17726,
            defaults={
                "name": "Machariel",
                "published": True,
                "eve_group": battleship_group,
            },
        )
        make_test_solar_system(
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            name="Amamake",
            position_x=0.0,
            position_y=0.0,
            position_z=0.0,
        )

    def setUp(self):
        make_capital_ping_channel()

    def test_build_capital_ping_payload(self):
        payload = make_killmail_payload(
            136500001,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=73790,
            attacker_count=5,
        )
        raw = payload["killmail"]
        built = build_capital_ping_payload(
            raw,
            zkb=payload["zkb"],
            distance_ly=0.0,
        )
        self.assertIn("embeds", built)
        self.assertIn("Amamake", built["embeds"][0]["title"])
        self.assertNotIn("content", built)

    @patch("feed.helpers.capital_pings.send_capital_ping_discord")
    def test_maybe_notify_capital_kill_sends_once(self, mock_send):
        mock_send.return_value = [999888777]
        payload = make_killmail_payload(
            136500002,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=73790,
            attacker_count=4,
        )

        self.assertTrue(maybe_notify_capital_kill(payload))
        self.assertFalse(maybe_notify_capital_kill(payload))
        self.assertEqual(FeedCapitalPing.objects.count(), 1)
        mock_send.assert_called_once()

    @patch("feed.helpers.capital_pings.send_capital_ping_discord")
    def test_maybe_notify_ignores_non_capital(self, mock_send):
        payload = make_killmail_payload(
            136500003,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=17726,
            attacker_ship_type_id=17726,
        )
        self.assertFalse(maybe_notify_capital_kill(payload))
        mock_send.assert_not_called()

    @patch("feed.helpers.capital_pings.send_capital_ping_discord")
    def test_maybe_notify_capital_on_field(self, mock_send):
        mock_send.return_value = [999888778]
        payload = make_killmail_payload(
            136500007,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=17726,
            attacker_ship_type_id=73790,
            attacker_count=6,
        )
        self.assertTrue(maybe_notify_capital_kill(payload))
        mock_send.assert_called_once()
        built = build_capital_ping_payload(
            payload["killmail"],
            zkb=payload["zkb"],
            distance_ly=0.0,
        )
        self.assertIn(
            "Capital ships involved",
            built["embeds"][0]["description"],
        )
        self.assertIn(
            "Revelation Navy Issue (attacking",
            built["embeds"][0]["description"],
        )

    @patch("feed.helpers.capital_pings.send_capital_ping_discord")
    def test_maybe_notify_ignores_out_of_range(self, mock_send):
        make_test_solar_system(
            solar_system_id=30000142,
            name="Jita",
            position_x=1.0e18,
            position_y=0.0,
            position_z=0.0,
            security_status=0.9,
        )
        payload = make_killmail_payload(
            136500004,
            solar_system_id=30000142,
            ship_type_id=73790,
        )
        self.assertFalse(maybe_notify_capital_kill(payload))
        mock_send.assert_not_called()

    @patch("feed.helpers.capital_pings.send_capital_ping_discord")
    def test_maybe_notify_skips_without_configured_channel(self, mock_send):
        DiscordChannel.objects.all().delete()
        payload = make_killmail_payload(
            136500006,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=73790,
        )
        self.assertFalse(maybe_notify_capital_kill(payload))
        mock_send.assert_not_called()

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_send_capital_ping_discord(self, mock_client_cls):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "1234567890"}
        mock_client.create_message.return_value = mock_response
        mock_client_cls.return_value = mock_client

        payload = make_killmail_payload(
            136500005,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=73790,
        )

        message_ids = send_capital_ping_discord(
            payload["killmail"],
            zkb=payload["zkb"],
            distance_ly=0.0,
            discord_client=mock_client,
        )
        self.assertEqual(message_ids, [1234567890])
        mock_client.create_message.assert_called_once()
