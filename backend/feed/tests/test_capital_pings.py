from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_tz
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone as dj_tz
from discord.models import DiscordChannel, DiscordGuild
from eveonline.models import EveCharacter
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
    CAPITAL_ALERT_TITLE,
    ZKILL_CHARACTER_URL,
    build_capital_alert_payload,
    build_capital_ping_payload,
    maybe_notify_capital_kill,
    send_capital_ping_discord,
)
from feed.helpers.capital_ships import (
    is_capital_ship_type,
    killmail_involves_capital,
)
from feed.helpers.system_distance import light_years_between_systems
from feed.models import FeedCapitalAlert, FeedCapitalPing
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


def _seed_ship_types() -> None:
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
    cruiser_group, _ = EveGroup.objects.get_or_create(
        id=26,
        defaults={
            "name": "Cruiser",
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
    EveType.objects.get_or_create(
        id=17715,
        defaults={
            "name": "Exequror Navy Issue",
            "published": True,
            "eve_group": cruiser_group,
        },
    )


class CapitalShipTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_ship_types()

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
        _seed_ship_types()
        make_test_solar_system(
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            name="Amamake",
            position_x=0.0,
            position_y=0.0,
            position_z=0.0,
        )

    def setUp(self):
        make_capital_ping_channel()
        esi_patcher = patch(
            "feed.helpers.eve_names._resolve_universe_names_via_esi",
            side_effect=lambda ids, missing_label="Entity": {
                int(entity_id): f"{missing_label} {entity_id}"
                for entity_id in ids
            },
        )
        esi_patcher.start()
        self.addCleanup(esi_patcher.stop)

    def test_build_capital_alert_payload_omits_kills_for_single_kill(self):
        built = build_capital_alert_payload(
            system_name="Amamake",
            distance_ly=0.0,
            capitals=[
                {
                    "type_id": 73790,
                    "name": "Revelation Navy Issue",
                    "role": "attacker",
                    "count": 1,
                    "characters": [
                        {
                            "character_id": 2111000001,
                            "name": "Dread Pilot",
                        }
                    ],
                }
            ],
            composition={
                "attacker_count": 4,
                "main_group": {
                    "id": 99000000,
                    "name": "Test Alliance",
                    "kind": "alliance",
                },
                "top_ship": {
                    "type_id": 73790,
                    "name": "Revelation Navy Issue",
                    "count": 1,
                },
            },
            kills=[
                {
                    "killmail_id": 1,
                    "ship_name": "Exequror Navy Issue",
                    "time_hhmm": "17:00",
                }
            ],
        )
        embed = built["embeds"][0]
        self.assertEqual(embed["title"], CAPITAL_ALERT_TITLE)
        self.assertIn("Amamake", embed["description"])
        self.assertIn("**Attackers:** 4", embed["description"])
        self.assertIn("**Main group:** Test Alliance", embed["description"])
        self.assertIn(
            "**Top attacking ship:** Revelation Navy Issue",
            embed["description"],
        )
        self.assertIn("Revelation Navy Issue", embed["description"])
        self.assertIn(
            "[Dread Pilot](https://zkillboard.com/character/2111000001/)",
            embed["description"],
        )
        self.assertNotIn("(victim)", embed["description"])
        self.assertNotIn("(attacking)", embed["description"])
        self.assertNotIn("Kills:", embed["description"])

    def test_build_capital_alert_payload_includes_kills_when_multiple(self):
        built = build_capital_alert_payload(
            system_name="Amamake",
            distance_ly=0.0,
            capitals=[
                {
                    "type_id": 73790,
                    "name": "Revelation Navy Issue",
                    "role": "attacker",
                    "count": 1,
                    "characters": [
                        {
                            "character_id": 2111000001,
                            "name": "Dread Pilot",
                        }
                    ],
                }
            ],
            kills=[
                {
                    "killmail_id": 1,
                    "ship_name": "Exequror Navy Issue",
                    "time_hhmm": "17:00",
                },
                {
                    "killmail_id": 2,
                    "ship_name": "Exequror Navy Issue",
                    "time_hhmm": "17:01",
                },
            ],
        )
        description = built["embeds"][0]["description"]
        self.assertIn(
            "Kills: Exequror Navy Issue (17:00), Exequror Navy Issue (17:01)",
            description,
        )

    def test_build_capital_alert_payload_system_chain(self):
        built = build_capital_alert_payload(
            system_name="Amamake",
            distance_ly=0.0,
            systems=[
                {
                    "solar_system_id": 30002084,
                    "system_name": "Aset",
                    "distance_ly": 3.2,
                },
                {
                    "solar_system_id": 30002090,
                    "system_name": "Frerstorn",
                    "distance_ly": 3.5,
                },
                {
                    "solar_system_id": AMAMAKE_SOLAR_SYSTEM_ID,
                    "system_name": "Amamake",
                    "distance_ly": 0.0,
                },
            ],
            capitals=[
                {
                    "type_id": 73790,
                    "name": "Revelation Navy Issue",
                    "role": "attacker",
                    "count": 1,
                    "characters": [
                        {
                            "character_id": 2111000001,
                            "name": "Dread Pilot",
                        }
                    ],
                }
            ],
            kills=[
                {
                    "killmail_id": 1,
                    "ship_name": "Exequror Navy Issue",
                    "time_hhmm": "17:00",
                }
            ],
        )
        description = built["embeds"][0]["description"]
        self.assertIn(
            "**System:** Aset → Frerstorn → Amamake",
            description,
        )
        self.assertIn("**Distance from Amamake:** 0.0 LY", description)

    def test_build_capital_ping_payload(self):
        victim_character_id = 80000001
        EveCharacter.objects.create(
            character_id=victim_character_id,
            character_name="Capital Victim",
        )
        payload = make_killmail_payload(
            136500001,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=73790,
            attacker_ship_type_id=17726,
            attacker_count=5,
        )
        raw = payload["killmail"]
        built = build_capital_ping_payload(
            raw,
            zkb=payload["zkb"],
            distance_ly=0.0,
        )
        self.assertIn("embeds", built)
        self.assertEqual(built["embeds"][0]["title"], CAPITAL_ALERT_TITLE)
        description = built["embeds"][0]["description"]
        self.assertIn("Amamake", description)
        self.assertIn("Revelation Navy Issue", description)
        self.assertIn("**Attackers:** 5", description)
        self.assertIn("**Main group:** Entity 99000000", description)
        self.assertIn(
            "**Top attacking ship:** Machariel ×5",
            description,
        )
        self.assertIn(
            f"[Capital Victim]({ZKILL_CHARACTER_URL.format(character_id=victim_character_id)})",
            description,
        )
        self.assertNotIn("(victim)", description)
        self.assertNotIn("content", built)

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_maybe_notify_creates_once_then_edits(self, mock_client_cls):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888777"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        first = make_killmail_payload(
            136500002,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=17715,
            attacker_ship_type_id=73790,
            attacker_count=4,
            killmail_time=datetime(2026, 7, 17, 17, 0, 0, tzinfo=dt_tz.utc),
        )
        second = make_killmail_payload(
            136500012,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=17715,
            attacker_ship_type_id=73790,
            attacker_count=4,
            killmail_time=datetime(2026, 7, 17, 17, 1, 0, tzinfo=dt_tz.utc),
        )

        self.assertTrue(maybe_notify_capital_kill(first))
        self.assertTrue(maybe_notify_capital_kill(second))
        self.assertFalse(maybe_notify_capital_kill(first))

        self.assertEqual(FeedCapitalAlert.objects.count(), 1)
        self.assertEqual(FeedCapitalPing.objects.count(), 2)
        mock_client.create_message.assert_called_once()
        mock_client.update_message.assert_called_once()

        alert = FeedCapitalAlert.objects.get()
        self.assertEqual(len(alert.kills), 2)
        self.assertEqual(len(alert.systems), 1)
        self.assertEqual(alert.systems[0]["system_name"], "Amamake")
        edit_payload = mock_client.update_message.call_args.kwargs["payload"]
        self.assertIn(
            "Kills: Exequror Navy Issue (17:00), Exequror Navy Issue (17:01)",
            edit_payload["embeds"][0]["description"],
        )

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_same_capital_crossing_systems_edits_chain(self, mock_client_cls):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888780"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        # ~1 LY from Amamake at origin (METERS_PER_LIGHT_YEAR ≈ 9.46e15).
        nearby_system_id = 30002084
        make_test_solar_system(
            solar_system_id=nearby_system_id,
            name="Aset",
            position_x=9.46e15,
            position_y=0.0,
            position_z=0.0,
        )

        first = make_killmail_payload(
            136500030,
            solar_system_id=nearby_system_id,
            ship_type_id=17715,
            attacker_ship_type_id=73790,
            attacker_count=1,
            killmail_time=datetime(2026, 7, 18, 14, 0, 0, tzinfo=dt_tz.utc),
        )
        second = make_killmail_payload(
            136500031,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=17715,
            attacker_ship_type_id=73790,
            attacker_count=1,
            killmail_time=datetime(2026, 7, 18, 14, 10, 0, tzinfo=dt_tz.utc),
        )

        self.assertTrue(maybe_notify_capital_kill(first))
        self.assertTrue(maybe_notify_capital_kill(second))

        self.assertEqual(FeedCapitalAlert.objects.count(), 1)
        self.assertEqual(FeedCapitalPing.objects.count(), 2)
        mock_client.create_message.assert_called_once()
        mock_client.update_message.assert_called_once()

        alert = FeedCapitalAlert.objects.get()
        self.assertEqual(alert.solar_system_id, AMAMAKE_SOLAR_SYSTEM_ID)
        self.assertEqual(
            [entry["system_name"] for entry in alert.systems],
            ["Aset", "Amamake"],
        )
        edit_payload = mock_client.update_message.call_args.kwargs["payload"]
        self.assertIn(
            "**System:** Aset → Amamake",
            edit_payload["embeds"][0]["description"],
        )

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_different_capitals_in_different_systems_stay_separate(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.side_effect = [{"id": "111"}, {"id": "222"}]
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        nearby_system_id = 30002090
        make_test_solar_system(
            solar_system_id=nearby_system_id,
            name="Frerstorn",
            position_x=9.46e15,
            position_y=0.0,
            position_z=0.0,
        )

        first = make_killmail_payload(
            136500040,
            solar_system_id=nearby_system_id,
            ship_type_id=17715,
            attacker_ship_type_id=73790,
            attacker_count=1,
        )
        second = make_killmail_payload(
            136500041,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=17715,
            attacker_ship_type_id=73790,
            attacker_count=1,
        )
        # Distinct capital pilot so character overlap does not chain alerts.
        second["killmail"]["attackers"][0]["character_id"] = 91000001

        self.assertTrue(maybe_notify_capital_kill(first))
        self.assertTrue(maybe_notify_capital_kill(second))
        self.assertEqual(FeedCapitalAlert.objects.count(), 2)
        self.assertEqual(mock_client.create_message.call_count, 2)
        mock_client.update_message.assert_not_called()

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_maybe_notify_ignores_non_capital(self, mock_client_cls):
        payload = make_killmail_payload(
            136500003,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=17726,
            attacker_ship_type_id=17726,
        )
        self.assertFalse(maybe_notify_capital_kill(payload))
        mock_client_cls.return_value.create_message.assert_not_called()

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_maybe_notify_capital_on_field(self, mock_client_cls):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888778"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        payload = make_killmail_payload(
            136500007,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=17726,
            attacker_ship_type_id=73790,
            attacker_count=6,
        )
        self.assertTrue(maybe_notify_capital_kill(payload))
        mock_client.create_message.assert_called_once()
        create_payload = mock_client.create_message.call_args.kwargs["payload"]
        description = create_payload["embeds"][0]["description"]
        self.assertIn("Revelation Navy Issue ×6", description)
        self.assertIn("**Attackers:** 6", description)
        self.assertIn("**Main group:** Entity 99000000", description)
        self.assertIn(
            "**Top attacking ship:** Revelation Navy Issue ×6",
            description,
        )
        self.assertIn(
            "[Pilot 90000000](https://zkillboard.com/character/90000000/)",
            description,
        )
        self.assertIn(
            "[Pilot 90000005](https://zkillboard.com/character/90000005/)",
            description,
        )

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_many_capitals_same_system_one_notification(self, mock_client_cls):
        """Thirty distinct capital pilots in one system still share one alert."""
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888790"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        for index in range(30):
            payload = make_killmail_payload(
                136500100 + index,
                solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
                ship_type_id=17715,
                attacker_ship_type_id=73790,
                attacker_count=1,
            )
            payload["killmail"]["attackers"][0]["character_id"] = (
                92000000 + index
            )
            self.assertTrue(maybe_notify_capital_kill(payload))

        self.assertEqual(FeedCapitalAlert.objects.count(), 1)
        self.assertEqual(FeedCapitalPing.objects.count(), 30)
        mock_client.create_message.assert_called_once()
        self.assertEqual(mock_client.update_message.call_count, 29)
        alert = FeedCapitalAlert.objects.get()
        self.assertEqual(len(alert.capitals[0]["characters"]), 30)
        self.assertEqual(alert.composition["attacker_count"], 1)

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_maybe_notify_ignores_out_of_range(self, mock_client_cls):
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
        mock_client_cls.return_value.create_message.assert_not_called()

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_maybe_notify_skips_without_configured_channel(
        self, mock_client_cls
    ):
        DiscordChannel.objects.all().delete()
        payload = make_killmail_payload(
            136500006,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=73790,
        )
        self.assertFalse(maybe_notify_capital_kill(payload))
        mock_client_cls.return_value.create_message.assert_not_called()

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_maybe_notify_age_gate_skips_old_kill(self, mock_client_cls):
        payload = make_killmail_payload(
            136500008,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=73790,
            killmail_time=datetime(2026, 6, 1, 12, 0, 0, tzinfo=dt_tz.utc),
        )
        self.assertIsNone(
            maybe_notify_capital_kill(payload, apply_age_gate=True)
        )
        mock_client_cls.return_value.create_message.assert_not_called()
        self.assertEqual(FeedCapitalPing.objects.count(), 0)

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_maybe_notify_age_gate_allows_fresh_kill(self, mock_client_cls):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888779"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        payload = make_killmail_payload(
            136500009,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=73790,
            killmail_time=dj_tz.now() - timedelta(minutes=5),
        )
        self.assertTrue(
            maybe_notify_capital_kill(payload, apply_age_gate=True)
        )
        mock_client.create_message.assert_called_once()

    @patch("feed.helpers.capital_pings.DiscordClient")
    def test_new_alert_after_session_expires(self, mock_client_cls):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.side_effect = [
            {"id": "111"},
            {"id": "222"},
        ]
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        first = make_killmail_payload(
            136500020,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=73790,
        )
        self.assertTrue(maybe_notify_capital_kill(first))
        alert = FeedCapitalAlert.objects.get()
        alert.last_activity_at = dj_tz.now() - timedelta(hours=2)
        alert.save(update_fields=["last_activity_at"])

        second = make_killmail_payload(
            136500021,
            solar_system_id=AMAMAKE_SOLAR_SYSTEM_ID,
            ship_type_id=73790,
        )
        self.assertTrue(maybe_notify_capital_kill(second))
        self.assertEqual(FeedCapitalAlert.objects.count(), 2)
        self.assertEqual(mock_client.create_message.call_count, 2)
        mock_client.update_message.assert_not_called()

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
