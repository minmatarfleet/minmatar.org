"""Trial tab and corp Members row insights."""

from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import Client, SimpleTestCase
from django.utils import timezone

from alliance.helpers.trial_peers import (
    build_peers,
    build_trial_lengths,
    compare_user,
    corp_trial_length,
    percentile,
    tier_index,
)
from alliance.helpers.trial_report import helpful_role
from alliance.models import AllianceHealthSnapshot
from app.test import TestCase
from app.testing import make_token
from eveonline.helpers.characters import set_primary_character
from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCorporation,
)
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from fleets.models import EveFleetInstance, EveFleetInstanceMember
from fleets.tests import make_test_fleet
from groups.models import UserCommunityStatus, UserCommunityStatusHistory


def _discord_signals():
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import group_post_save, user_group_changed

    return (
        (
            django_signals.m2m_changed,
            user_group_changed,
            User.groups.through,
            "user_group_changed",
        ),
        (django_signals.post_save, group_post_save, Group, "group_post_save"),
    )


def setUpModule():
    # A trial status syncs community groups, which would create Discord roles.
    for signal, receiver, sender, uid in _discord_signals():
        signal.disconnect(receiver, sender=sender, dispatch_uid=uid)


def tearDownModule():
    for signal, receiver, sender, uid in _discord_signals():
        signal.connect(receiver, sender=sender, dispatch_uid=uid)


CORP_ID = 98000001
HURRICANE = 24702
STABBER = 622
RIFTER = 587
SABRE = 22456


class TierMathTestCase(SimpleTestCase):
    def test_percentile_splits_ties(self):
        self.assertEqual(percentile(0, [0, 0, 0, 0]), 50)
        self.assertEqual(percentile(5, [1, 2, 3, 4]), 100)
        self.assertEqual(percentile(0, [1, 2, 3, 4]), 0)
        self.assertIsNone(percentile(3, []))

    def test_tiers_are_fifths(self):
        self.assertEqual(
            [tier_index(p) for p in (0, 19, 20, 39, 40, 59, 60, 79, 80, 100)],
            [0, 0, 1, 1, 2, 2, 3, 3, 4, 4],
        )

    def test_compare_reads_peers(self):
        peers = build_peers(
            active_user_ids={1, 2, 3, 4},
            member_user_ids={1, 2, 3, 4, 9},
            fleets_30d={1: 1, 2: 2, 3: 3, 4: 4, 9: 9},
            kills_30d={9: 0},
            voice_hours_30d={1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0},
        )
        payload = {"hygiene": {"peers": peers}}
        tiers = {
            row["signal"]: row["tier"] for row in compare_user(payload, 9)
        }
        self.assertEqual(
            tiers,
            {
                "fleets": "well_above",
                "kills": "average",
                "voice": "well_below",
            },
        )
        self.assertIsNone(compare_user(payload, 42))
        self.assertIsNone(compare_user(None, 9))

    def test_secondary_fits_only_help_from_academy_pilots(self):
        self.assertTrue(helpful_role("support", academy=False))
        self.assertFalse(helpful_role("secondary", academy=False))
        self.assertTrue(helpful_role("secondary", academy=True))
        self.assertFalse(helpful_role("off_doctrine", academy=True))
        self.assertFalse(helpful_role(None, academy=False))

    def test_corp_average_needs_three_trials(self):
        payload = {
            "hygiene": {
                "trial_lengths": {
                    "by_corp": {
                        "1": {"days": 50, "count": 2},
                        "2": {"days": 72, "count": 5},
                    },
                    "alliance": {"days": 65, "count": 40},
                }
            }
        }
        self.assertEqual(corp_trial_length(payload, 2)["scope"], "corporation")
        self.assertEqual(
            corp_trial_length(payload, 1),
            {"days": 65, "count": 40, "scope": "alliance"},
        )


class TrialLengthTestCase(TestCase):
    def _change(self, user, from_status, to_status, days_ago):
        row = UserCommunityStatusHistory.objects.create(
            user=user, from_status=from_status, to_status=to_status
        )
        # changed_at is auto_now_add.
        UserCommunityStatusHistory.objects.filter(pk=row.pk).update(
            changed_at=timezone.now() - timedelta(days=days_ago)
        )

    def test_trial_to_active_days_per_corp(self):
        quick = User.objects.create(username="quick")
        slow = User.objects.create(username="slow")
        still = User.objects.create(username="still")
        self._change(quick, None, "trial", 100)
        self._change(quick, "trial", "active", 40)
        self._change(slow, None, "trial", 200)
        self._change(slow, "trial", "active", 120)
        self._change(still, None, "trial", 30)
        lengths = build_trial_lengths(
            now=timezone.now(),
            primary_corp={quick.id: CORP_ID, slow.id: CORP_ID},
        )
        self.assertEqual(
            lengths["by_corp"][str(CORP_ID)], {"days": 70, "count": 2}
        )
        self.assertEqual(lengths["alliance"], {"days": 70, "count": 2})


class TrialEndpointsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        EveCorporation.objects.create(
            corporation_id=CORP_ID, name="Fosfo Test", ticker="FOSFO"
        )
        self.character = EveCharacter.objects.create(
            character_id=2001,
            character_name="Vosk Arran",
            user=self.user,
            corporation_id=CORP_ID,
        )
        set_primary_character(self.user, self.character)
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_TRIAL
        )
        self.client = Client()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        self.doctrine = EveDoctrine.objects.create(
            name="Vagabonds", type="non_strategic", description=""
        )
        for name, ship_id, role in (
            ("Hurricane", HURRICANE, "primary"),
            ("Stabber", STABBER, "secondary"),
            ("Sabre", SABRE, "support"),
        ):
            fitting = EveFitting.objects.create(
                name=name, ship_id=ship_id, description="", eft_format=""
            )
            EveDoctrineFitting.objects.create(
                doctrine=self.doctrine, fitting=fitting, role=role
            )
        self._fleet_with(HURRICANE)
        self._fleet_with(STABBER)
        self._fleet_with(RIFTER)
        self._fleet_with(SABRE)
        AllianceHealthSnapshot.objects.create(
            computed_at=timezone.now(),
            payload={
                "hygiene": {
                    "trial": {
                        "buckets": {
                            "too_early": [
                                {
                                    "user_id": self.user.id,
                                    "alliance_days": 41,
                                    "decision": "too_early",
                                }
                            ]
                        }
                    },
                    "peers": build_peers(
                        active_user_ids={101, 102, 103},
                        member_user_ids={101, 102, 103, self.user.id},
                        fleets_30d={101: 1, 102: 2, 103: 3, self.user.id: 4},
                        kills_30d={101: 5, 102: 5, 103: 5},
                        voice_hours_30d={101: 1.0, 102: 2.0, 103: 3.0},
                    ),
                    "trial_lengths": {
                        "by_corp": {str(CORP_ID): {"days": 72, "count": 4}},
                        "alliance": {"days": 70, "count": 30},
                    },
                }
            },
        )

    def _fleet_with(self, ship_id):
        fleet = make_test_fleet("Roam", self.user, start=timezone.now())
        fleet.doctrine = self.doctrine
        fleet.save()
        instance = EveFleetInstance.objects.create(
            id=7000 + ship_id, eve_fleet=fleet, last_updated=timezone.now()
        )
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=self.character.character_id,
            character_name=self.character.character_name,
            ship_type_id=ship_id,
            ship_name=f"Ship {ship_id}",
            solar_system_id=1,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
            join_time=timezone.now(),
        )

    def test_not_on_trial(self):
        UserCommunityStatus.objects.filter(user=self.user).update(
            status=UserCommunityStatus.STATUS_ACTIVE
        )
        response = self.client.get("/api/alliance/trial/me", **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["on_trial"], False)
        self.assertIsNone(response.json()["trial"])
        status = self.client.get("/api/alliance/trial/me/status", **self.auth)
        self.assertEqual(status.json(), {"on_trial": False})

    def test_my_trial(self):
        response = self.client.get("/api/alliance/trial/me", **self.auth)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["on_trial"])
        self.assertEqual(data["corporation_ticker"], "FOSFO")
        self.assertEqual(
            data["trial"],
            {
                "day": 41,
                "review_day": 60,
                "scale_days": 90,
                "average_days": 72,
                "average_scope": "corporation",
                "on_pace": True,
            },
        )
        tiers = {row["signal"]: row["tier"] for row in data["compare"]}
        self.assertEqual(
            tiers,
            {
                "fleets": "well_above",
                "kills": "well_below",
                "voice": "well_below",
            },
        )
        # Hurricane (primary) and Sabre (support) help; Stabber is an
        # Academy fit and the Rifter is off doctrine.
        self.assertEqual(data["ships"]["doctrine_fleets"], 4)
        self.assertEqual(data["ships"]["helpful_fleets"], 2)
        roles = {
            fleet["ship_type_id"]: fleet["role"] for fleet in data["fleets"]
        }
        self.assertEqual(
            roles,
            {
                HURRICANE: "primary",
                STABBER: "secondary",
                RIFTER: "off_doctrine",
                SABRE: "support",
            },
        )

    def test_member_insights_need_leadership(self):
        viewer = User.objects.create(username="viewer")
        response = self.client.get(
            f"/api/eveonline/corporations/corporations/{CORP_ID}/members/2001/insights",
            HTTP_AUTHORIZATION=f"Bearer {make_token(viewer)}",
        )
        self.assertEqual(response.status_code, 403)

    def test_member_insights(self):
        boss = User.objects.create(username="boss", is_superuser=True)
        killmail = EveCharacterKillmail.objects.create(
            id=1,
            killmail_id=1,
            killmail_hash="h1",
            killmail_time=timezone.now(),
            solar_system_id=1,
            ship_type_id=RIFTER,
            victim_character_id=999,
            attackers="[]",
            items="[]",
            character=self.character,
        )
        EveCharacterKillmailAttacker.objects.create(
            killmail=killmail, character_id=2001, ship_type_id=HURRICANE
        )
        EveCharacterKillmailAttacker.objects.create(
            killmail=killmail, character_id=3001
        )
        response = self.client.get(
            f"/api/eveonline/corporations/corporations/{CORP_ID}/members/2001/insights",
            HTTP_AUTHORIZATION=f"Bearer {make_token(boss)}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["trial"]["day"], 41)
        self.assertEqual(data["ships"]["helpful_fleets"], 2)
        self.assertEqual(
            {
                k: data["kills"][k]
                for k in ("solo", "small_gang", "fleet", "losses")
            },
            {"solo": 0, "small_gang": 1, "fleet": 0, "losses": 0},
        )
        self.assertEqual(data["kills"]["top_ship_type_id"], HURRICANE)

    def test_member_insights_404_outside_corp(self):
        boss = User.objects.create(username="boss", is_superuser=True)
        EveCharacter.objects.create(
            character_id=5005, character_name="Elsewhere", corporation_id=1
        )
        response = self.client.get(
            f"/api/eveonline/corporations/corporations/{CORP_ID}/members/5005/insights",
            HTTP_AUTHORIZATION=f"Bearer {make_token(boss)}",
        )
        self.assertEqual(response.status_code, 404)
