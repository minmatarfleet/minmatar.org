import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.utils import timezone
from eveuniverse.models import (
    EveCategory,
    EveConstellation,
    EveGroup,
    EveRegion,
    EveSolarSystem,
    EveType,
)

from app.test import TestCase
from app.testing import auth_headers
from discord.models import DiscordChannel, DiscordGuild
from eveonline.models import (
    EveCharacter,
    EveCharacterFwLpPayout,
    EveCorporation,
    EveLocation,
    FwPayoutEventCode,
)
from fittings.models import (
    DOCTRINE_TYPE_STRATEGIC,
    EveDoctrine,
    EveDoctrineChangeRequest,
)
from fleets.models import NpsiEventSource
from groups.features.gate_manifest import load_gates
from groups.helpers.feature_access import clear_feature_cache
from manage_hub.screens import GATES, SCREENS
from manage_hub.summary import QUEUES
from reddit.models import RedditPostChangeRequest, RedditPostTemplate
from users.helpers import add_user_permission

SCREENS_JSON = (
    Path(settings.BASE_DIR).parent
    / "frontend"
    / "app"
    / "src"
    / "json"
    / "manage_screens.json"
)


class ManageApiTestCase(TestCase):
    def setUp(self):
        super().setUp()
        clear_feature_cache()
        self.client = Client()
        self.root = User.objects.create_superuser("root", "r@x", "pw")

    def tearDown(self):
        clear_feature_cache()

    def get(self, path, user=None):
        return self.client.get(
            f"/api/manage{path}", **auth_headers(user or self.user)
        )

    def grant(self, user, *codenames):
        for dotted in codenames:
            add_user_permission(user, dotted.split(".")[1])
        clear_feature_cache()
        return User.objects.get(pk=user.pk)


class RegistryParityTestCase(TestCase):
    """The backend's copy of the hub registry matches the site's."""

    def setUp(self):
        super().setUp()
        with open(SCREENS_JSON, encoding="utf-8") as handle:
            self.site = json.load(handle)

    def test_screens_match_manage_screens_json(self):
        site = [
            (
                row["key"],
                row["group"],
                row.get("gate", ""),
                row.get("check", ""),
            )
            for row in self.site["screens"]
        ]
        backend = [(s.key, s.group, s.gate, s.check) for s in SCREENS]
        self.assertEqual(site, backend)
        self.assertEqual(
            sorted({row[1] for row in site}), sorted(self.site["groups"])
        )

    def test_queues_match_manage_screens_json(self):
        site = [(row["key"], row["screen"]) for row in self.site["queues"]]
        self.assertEqual(site, [(key, screen) for key, screen, _ in QUEUES])

    def test_gates_match_feature_gates_json(self):
        manifest = {gate.key: gate for gate in load_gates()}
        for key, gate in GATES.items():
            with self.subTest(gate=key):
                site = manifest[key]
                self.assertEqual(site.feature, gate.feature)
                self.assertEqual(site.perms, gate.perms)
                self.assertEqual(site.superuser, gate.superuser)
                self.assertEqual(site.custom, gate.custom)


class SummaryTestCase(ManageApiTestCase):
    def test_requires_sign_in(self):
        self.assertEqual(
            401, self.client.get("/api/manage/summary").status_code
        )

    def test_plain_pilot_reaches_nothing(self):
        body = self.get("/summary").json()
        self.assertEqual(
            {"role": "manager", "screens": [], "queues": [], "total": 0}, body
        )

    def test_superuser_reaches_every_gated_screen(self):
        body = self.get("/summary", self.root).json()
        self.assertEqual("superuser", body["role"])
        keys = [row["key"] for row in body["screens"]]
        # LP desk and alliance health ask their own API checks.
        expected = [s.key for s in SCREENS if s.check != "alliance_health"]
        self.assertEqual(expected, [k for k in keys if k != "alliance_health"])
        self.assertEqual(
            ["doctrine_changes", "reddit_posts", "payout_codes", "npsi_feeds"],
            [row["key"] for row in body["queues"]],
        )
        self.assertEqual(0, body["total"])

    def test_one_permission_opens_its_screens_only(self):
        user = self.grant(self.user, "campaigns.change_campaign")
        body = self.get("/summary", user).json()
        self.assertEqual(
            [
                {"key": "campaigns", "group": "fleets"},
                {"key": "payout_codes", "group": "fleets"},
            ],
            body["screens"],
        )
        self.assertEqual(["payout_codes"], [q["key"] for q in body["queues"]])

    @override_settings(FRONTEND_GATE_SOURCE="features")
    def test_features_mode_reads_pilot_features(self):
        self.assertEqual([], self.get("/summary").json()["screens"])
        self.assertTrue(self.get("/summary", self.root).json()["screens"])

    def test_reddit_queue_counts_changes_and_first_approvals(self):
        user = self.grant(self.user, "reddit.change_redditpostchangerequest")
        ceo = EveCharacter.objects.create(
            character_id=91000001, character_name="Rat CEO", user=self.user
        )
        first = EveCorporation.objects.create(
            corporation_id=98000001, name="Rattini Tribe", ceo=ceo
        )
        second = EveCorporation.objects.create(
            corporation_id=98000002, name="Second Corp"
        )
        third = EveCorporation.objects.create(
            corporation_id=98000003, name="Untitled Corp"
        )
        approved = RedditPostTemplate.objects.create(
            corporation=first, title="Join", content="Fly", approved=True
        )
        change = RedditPostChangeRequest.objects.create(
            template=approved, title="Join us", content="Fly more"
        )
        RedditPostChangeRequest.objects.filter(pk=change.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        RedditPostTemplate.objects.create(
            corporation=second, title="New", content="Words"
        )
        # Not ready for review: no title yet.
        RedditPostTemplate.objects.create(corporation=third, title="")

        queue = self._queue(user, "reddit_posts")
        self.assertEqual(2, queue["count"])
        self.assertEqual("Rattini Tribe", queue["next_label"])
        self.assertIsNotNone(queue["oldest_at"])

    def test_payout_queue_lists_unmapped_recent_codes(self):
        character = EveCharacter.objects.create(
            character_id=91000002, character_name="Plexer"
        )
        FwPayoutEventCode.objects.get_or_create(
            event_code=359, defaults={"site_kind": "small"}
        )
        for notification_id, code, age_days in (
            (1, 359, 1),
            (2, 777, 3),
            (3, 777, 2),
            (4, 888, 1),
            (5, 999, 45),
        ):
            EveCharacterFwLpPayout.objects.create(
                character=character,
                notification_id=notification_id,
                notification_type="FacWarLPPayoutKill",
                occurred_at=timezone.now() - timedelta(days=age_days),
                amount_lp=500,
                event_code=code,
            )
        queue = self._queue(self.root, "payout_codes")
        self.assertEqual(2, queue["count"])
        self.assertEqual("777", queue["next_label"])

    def test_npsi_queue_counts_enabled_failing_feeds(self):
        # A data migration seeds the real feeds; start from none.
        NpsiEventSource.objects.all().delete()
        failing = NpsiEventSource.objects.create(
            name="Unaligned test",
            feed_url="https://example.com/a.json",
            fc_character_name="FC",
            last_error="HTTP 500",
            last_success_at=timezone.now() - timedelta(hours=5),
        )
        NpsiEventSource.objects.create(
            name="Healthy",
            feed_url="https://example.com/b.json",
            fc_character_name="FC",
        )
        NpsiEventSource.objects.create(
            name="Off",
            feed_url="https://example.com/c.json",
            fc_character_name="FC",
            enabled=False,
            last_error="HTTP 404",
        )
        queue = self._queue(self.root, "npsi_feeds")
        self.assertEqual(1, queue["count"])
        self.assertEqual("warn", queue["tone"])
        self.assertEqual(failing.name, queue["next_label"])

    def test_doctrine_queue_counts_reviewable_requests(self):
        doctrine = EveDoctrine.objects.create(
            name="Rifter Roam", type=DOCTRINE_TYPE_STRATEGIC, description=""
        )
        EveDoctrineChangeRequest.objects.create(
            doctrine=doctrine, tier="strategic", payload={}
        )
        EveDoctrineChangeRequest.objects.create(
            doctrine=doctrine,
            tier="strategic",
            payload={},
            status="approved",
        )
        queue = self._queue(self.root, "doctrine_changes")
        self.assertEqual(1, queue["count"])
        self.assertEqual("Rifter Roam", queue["next_label"])
        body = self.get("/summary", self.root).json()
        self.assertEqual(1, body["total"])

    def _queue(self, user, key):
        body = self.get("/summary", user).json()
        return next(row for row in body["queues"] if row["key"] == key)


class SearchTestCase(ManageApiTestCase):
    def test_unknown_kind_is_refused(self):
        self.assertEqual(
            400, self.get("/search?kind=planet&q=Ama").status_code
        )

    def test_short_query_returns_nothing(self):
        response = self.get("/search?kind=system&q=A")
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())

    def test_systems_by_name_prefix_first(self):
        region = EveRegion.objects.create(id=10000030, name="Heimatar")
        constellation = EveConstellation.objects.create(
            id=20000334,
            name="Anher",
            eve_region=region,
            position_x=0,
            position_y=0,
            position_z=0,
        )
        for system_id, name in ((30002537, "Amamake"), (30002538, "Hamam")):
            EveSolarSystem.objects.create(
                id=system_id,
                name=name,
                eve_constellation=constellation,
                security_status=0.4,
                position_x=0,
                position_y=0,
                position_z=0,
                enabled_sections=0,
            )
        rows = self.get("/search?kind=system&q=ama").json()
        self.assertEqual(["Amamake", "Hamam"], [row["name"] for row in rows])
        self.assertEqual("30002537", rows[0]["id"])
        self.assertEqual("0.4 · Heimatar", rows[0]["detail"])

    def test_types_and_ships_carry_icons(self):
        ships = EveCategory.objects.create(id=6, name="Ship", published=True)
        material = EveCategory.objects.create(
            id=4, name="Material", published=True
        )
        frigate = EveGroup.objects.create(
            id=25, name="Frigate", eve_category=ships, published=True
        )
        mineral = EveGroup.objects.create(
            id=18, name="Mineral", eve_category=material, published=True
        )
        EveType.objects.create(
            id=587, name="Rifter", eve_group=frigate, published=True
        )
        EveType.objects.create(
            id=34, name="Riftanium", eve_group=mineral, published=True
        )
        ships_found = self.get("/search?kind=ship&q=rift").json()
        self.assertEqual(["Rifter"], [row["name"] for row in ships_found])
        self.assertEqual("Frigate", ships_found[0]["detail"])
        self.assertIn("/types/587/icon", ships_found[0]["icon_url"])
        types_found = self.get("/search?kind=type&q=rift").json()
        self.assertEqual(
            ["Riftanium", "Rifter"], [row["name"] for row in types_found]
        )

    def test_corporations_reuse_the_entity_search(self):
        EveCorporation.objects.create(
            corporation_id=98000001, name="Rattini Tribe", ticker="RAT"
        )
        rows = self.get("/search?kind=corporation&q=Ratt").json()
        self.assertEqual("Rattini Tribe", rows[0]["name"])
        self.assertEqual("RAT", rows[0]["detail"])
        self.assertIn("/corporations/98000001/logo", rows[0]["icon_url"])

    def test_locations_match_station_or_system(self):
        EveLocation.objects.create(
            location_id=1022734985679,
            location_name="Amamake - 3 Time Nearly AT Winners",
            solar_system_id=30002537,
            solar_system_name="Amamake",
            short_name="Amamake",
        )
        rows = self.get("/search?kind=location&q=amam").json()
        self.assertEqual("1022734985679", rows[0]["id"])
        self.assertEqual("Amamake", rows[0]["detail"])

    def test_people_and_channels_are_for_managers(self):
        guild = DiscordGuild.objects.create(guild_id=777001, name="Minmatar")
        DiscordChannel.objects.create(
            channel_id=1234567890123456789,
            guild=guild,
            name="lp-buyback",
            channel_type=DiscordChannel.TEXT,
        )
        EveCharacter.objects.create(
            character_id=91000003, character_name="Pilot One", user=self.user
        )
        for kind, q in (("discord_channel", "buy"), ("character", "pilot")):
            with self.subTest(kind=kind):
                self.assertEqual(
                    403, self.get(f"/search?kind={kind}&q={q}").status_code
                )
        channels = self.get(
            "/search?kind=discord_channel&q=buy", self.root
        ).json()
        # Snowflakes stay exact as strings.
        self.assertEqual("1234567890123456789", channels[0]["id"])
        self.assertEqual("#lp-buyback", channels[0]["name"])
        self.assertEqual("Text · Minmatar", channels[0]["detail"])
        pilots = self.get("/search?kind=character&q=pilot", self.root).json()
        self.assertEqual(["Pilot One"], [row["name"] for row in pilots])
