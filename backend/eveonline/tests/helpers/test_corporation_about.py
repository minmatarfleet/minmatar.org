"""About-tab rollups and Members roster facts for a corporation."""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from alliance.models import AllianceHealthSnapshot
from app.test import TestCase
from eveonline.helpers.corporations import stats_cache
from eveonline.helpers.corporations.about import (
    corporation_about,
    member_facts,
    prime_windows,
)
from eveonline.models import (
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCorporation,
    EvePlayer,
)
from eveonline.tasks.corporations import refresh_corporation_profile_stats
from eveonline.tests.helpers.test_corporation_public_summary import (
    _disconnect_external_signals,
    _ship_groups,
)
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from groups.models import UserCommunityStatusHistory
from tribes.models import Tribe, TribeGroup, TribeGroupMembership

CORP_ID = 98726134
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=dt_timezone.utc)


class CorporationAboutTestCase(TestCase):
    def setUp(self):
        cache.clear()
        _disconnect_external_signals()
        super().setUp()
        self.client = Client()
        self.corporation = EveCorporation.objects.create(
            corporation_id=CORP_ID,
            name="Rattini Tribe",
            timezones="AUTZ (10:00 - 13:00)\r\nEUTZ (16:00 - 20:00)\r\nUSTZ (22:00 - 02:00)",
        )
        self.types = _ship_groups()
        self.history_id = 0

    def test_prime_windows_parse_free_text_and_count_bracket_pilots(self):
        windows = prime_windows(
            self.corporation.timezones,
            # A pilot in EUTZ and EUTZ+ counts once for EU.
            {1: ["EUTZ", "EUTZ+", "AUTZ"], 2: ["EUTZ+"], 3: ["USTZ"]},
        )
        self.assertEqual(
            [
                {"zone": "AU", "start_hour": 10, "end_hour": 13, "pilots": 1},
                {"zone": "EU", "start_hour": 16, "end_hour": 20, "pilots": 2},
                {"zone": "US", "start_hour": 22, "end_hour": 2, "pilots": 1},
            ],
            windows,
        )
        self.assertEqual([], prime_windows("Whenever", {}))

    def test_tenure_counts_mains_only_and_founders(self):
        veteran = self._user("veteran")
        main = self._character(301, "Veteran Main", veteran, main=True)
        alt = self._character(302, "Veteran Alt", veteran)
        newbie = self._user("newbie")
        new_main = self._character(303, "Newbie", newbie, main=True)
        self._stint(main, NOW - timedelta(days=800))
        # A long-held alt must not lift the person's tenure.
        self._stint(alt, NOW - timedelta(days=2000))
        self._stint(new_main, NOW - timedelta(days=40))
        self.corporation.date_founded = NOW - timedelta(days=810)
        self.corporation.save()

        about = self._about()
        self.assertEqual(2, about["tenure"]["mains"])
        self.assertEqual(420, about["tenure"]["average_days"])
        self.assertEqual(
            [
                {"key": "two_years", "count": 1},
                {"key": "one_year", "count": 0},
                {"key": "three_months", "count": 0},
                {"key": "new", "count": 1},
            ],
            about["tenure"]["bands"],
        )
        self.assertEqual(1, about["founders"])
        self.assertEqual(
            self.corporation.date_founded.isoformat(), about["founded"]
        )

    def test_founded_falls_back_to_earliest_corp_history(self):
        pilot = self._user("pilot")
        main = self._character(311, "Pilot", pilot, main=True)
        start = NOW - timedelta(days=500)
        self._stint(main, start)
        self.assertEqual(start.isoformat(), self._about()["founded"])

    def test_fleet_rollups_fold_alts_and_skip_pods(self):
        fc = self._user("fc")
        fc_main = self._character(401, "FC Main", fc, main=True)
        fc_alt = self._character(402, "FC Alt", fc)
        line = self._user("line")
        line_main = self._character(403, "Line Main", line, main=True)
        unlinked = self._character(404, "Unlinked", None)
        battleship = self.types["battleship"]
        capsule = self.types["capsule"]
        saturday = datetime(2026, 9, 19, 18, 30, tzinfo=dt_timezone.utc)
        big = self._fleet(
            1, fc, saturday, "Fortizar timer\nForm up in Amamake"
        )
        self._attend(fc_main, big, battleship, saturday)
        self._attend(fc_alt, big, battleship, saturday)
        self._attend(line_main, big, capsule, saturday)
        self._attend(unlinked, big, battleship, saturday)
        small = self._fleet(2, fc, saturday - timedelta(days=30), "Roam")
        self._attend(
            line_main, small, battleship, saturday - timedelta(days=30)
        )

        about = self._about()
        # The FC and their alt are one person in the 18:00 Saturday cell.
        self.assertEqual(3, about["heatmap"][5][18])
        self.assertEqual(
            [{"type_id": battleship, "name": "Battleship", "pilots": 3}],
            about["hulls"],
        )
        self.assertEqual(
            {
                "pilots": 3,
                "date": saturday.isoformat(),
                "title": "Fortizar timer",
            },
            about["records"]["biggest_turnout"],
        )
        self.assertEqual(
            {"month": "2026-09", "fleets": 1},
            about["records"]["busiest_month"],
        )
        self.assertEqual(
            [
                {
                    "character_id": 403,
                    "character_name": "Line Main",
                    "value": 2,
                },
                {"character_id": 401, "character_name": "FC Main", "value": 1},
            ],
            about["leaderboards"]["fleets"],
        )
        self.assertEqual(
            [{"character_id": 401, "character_name": "FC Main", "value": 2}],
            about["leaderboards"]["fleets_led"],
        )
        self.assertEqual(
            {"name": "Amamake", "share": 1.0}, about["home_system"]
        )

    def test_fleets_led_skips_cancelled_campaign_and_future_fleets(self):
        fc = self._user("fc")
        self._character(411, "FC Main", fc, main=True)
        for offset_days, fleet_type, status in (
            (-2, "training", "complete"),
            (-3, "strategic", "pending"),
            (-4, "training", "cancelled"),
            (-5, "standing", "active"),
            (-6, "gang", "complete"),
            (3, "strategic", "pending"),
        ):
            EveFleet.objects.create(
                start_time=NOW + timedelta(days=offset_days),
                type=fleet_type,
                status=status,
                created_by=fc,
            )

        self.assertEqual(
            [{"character_id": 411, "character_name": "FC Main", "value": 2}],
            self._about()["leaderboards"]["fleets_led"],
        )

    def test_leaderboards_count_all_time(self):
        fc = self._user("fc")
        fc_main = self._character(421, "FC Main", fc, main=True)
        fc_alt = self._character(422, "FC Alt", fc)
        battleship = self.types["battleship"]
        for instance_id, days_ago in ((11, 5), (12, 200), (13, 900)):
            when = NOW - timedelta(days=days_ago)
            fleet = self._fleet(instance_id, fc, when, "Ops")
            self._attend(fc_main, fleet, battleship, when)
            self._attend(fc_alt, fleet, battleship, when)
        for killmail_id, days_ago in ((31, 10), (32, 400), (33, 1200)):
            self._kill(
                killmail_id, [fc_main, fc_alt], NOW - timedelta(days=days_ago)
            )

        leaderboards = self._about()["leaderboards"]
        expected = [
            {"character_id": 421, "character_name": "FC Main", "value": 3}
        ]
        self.assertEqual(expected, leaderboards["fleets"])
        self.assertEqual(expected, leaderboards["kills"])
        self.assertEqual(expected, leaderboards["fleets_led"])

    def test_tribe_groups_count_people_once(self):
        pilot = self._user("tribal")
        self._character(501, "Tribal", pilot, main=True)
        tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        dreads = TribeGroup.objects.create(tribe=tribe, name="Dreads")
        TribeGroupMembership.objects.create(
            user=pilot, tribe_group=dreads, status="active"
        )
        self.assertEqual(
            [{"name": "Dreads", "members": 1}], self._about()["tribe_groups"]
        )

    def test_member_facts_weekly_last_fleet_and_top_hull(self):
        pilot = self._user("weekly")
        main = self._character(601, "Weekly", pilot, main=True)
        self._stint(main, NOW - timedelta(days=100))
        fleet = self._fleet(3, pilot, NOW - timedelta(days=3), "Ops")
        self._attend(
            main, fleet, self.types["capsule"], NOW - timedelta(days=3)
        )
        self._attend(
            main, fleet, self.types["battleship"], NOW - timedelta(days=3)
        )
        old = self._fleet(4, pilot, NOW - timedelta(days=20), "Old ops")
        self._attend(
            main, old, self.types["battleship"], NOW - timedelta(days=20)
        )

        facts = member_facts([main], self.corporation, now=NOW)[601]
        self.assertEqual(13, len(facts["weekly_fleets"]))
        self.assertEqual(1, facts["weekly_fleets"][-1])
        self.assertEqual(1, facts["weekly_fleets"][-3])
        self.assertEqual(self.types["battleship"], facts["top_hull_id"])
        self.assertEqual(
            (NOW - timedelta(days=100)).isoformat(), facts["corp_joined_at"]
        )
        self.assertIsNotNone(facts["last_fleet_at"])

    def test_member_facts_count_a_fleet_once_per_person(self):
        pilot = self._user("multibox")
        main = self._character(651, "Box Main", pilot, main=True)
        alt = self._character(652, "Box Alt", pilot)
        when = NOW - timedelta(days=2)
        fleet = self._fleet(5, pilot, when, "Ops")
        self._attend(main, fleet, self.types["battleship"], when)
        self._attend(alt, fleet, self.types["logistics"], when)

        facts = member_facts([main, alt], self.corporation, now=NOW)
        self.assertEqual(1, facts[651]["person_fleets_90d"])
        self.assertEqual(
            facts[651]["weekly_fleets"], facts[652]["weekly_fleets"]
        )
        self.assertEqual(1, sum(facts[651]["weekly_fleets"]))

    def test_members_endpoint_adds_facts_history_and_trial_review(self):
        self.make_superuser()
        trialist = self._user("trialist")
        self._character(701, "Trialist", trialist, main=True)
        UserCommunityStatusHistory.objects.create(
            user=trialist, from_status=None, to_status="trial"
        )
        AllianceHealthSnapshot.objects.create(
            computed_at=timezone.now(),
            payload={
                "hygiene": {
                    "trial": {
                        "buckets": {
                            "approve": [
                                {
                                    "user_id": trialist.id,
                                    "reason": "4 fleets in 90d",
                                }
                            ]
                        }
                    }
                }
            },
        )
        stats_cache.refresh_corporation_stats(self.corporation)
        with patch.object(refresh_corporation_profile_stats, "apply_async"):
            response = self.client.get(
                f"/api/eveonline/corporations/corporations/{CORP_ID}/members",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(200, response.status_code)
        row = next(r for r in response.json() if r["character_id"] == 701)
        self.assertTrue(row["trial_ready"])
        self.assertEqual("4 fleets in 90d", row["trial_reason"])
        self.assertEqual("trial", row["status_history"][0]["to_status"])
        self.assertEqual(13, len(row["weekly_fleets"]))

    def test_info_endpoint_serves_about_from_cache(self):
        pilot = self._user("info")
        self._character(801, "Info", pilot, main=True)
        stats_cache.refresh_corporation_stats(self.corporation)
        response = self.client.get(
            f"/api/eveonline/corporations/corporations/{CORP_ID}/info"
        )
        self.assertEqual(200, response.status_code)
        about = response.json()["about"]
        self.assertEqual(3, len(about["prime_windows"]))
        self.assertEqual(7, len(about["heatmap"]))

    def _about(self):
        characters = list(EveCharacter.objects.filter(corporation_id=CORP_ID))
        with patch(
            "eveonline.helpers.corporations.about.timezone.now",
            return_value=NOW,
        ):
            return corporation_about(
                self.corporation,
                characters,
                {},
                now=NOW,
            )

    def _user(self, username):
        return User.objects.create_user(username=username)

    def _character(self, character_id, name, user, main=False):
        character = EveCharacter.objects.create(
            character_id=character_id,
            character_name=name,
            corporation_id=CORP_ID,
            user=user,
        )
        if main:
            EvePlayer.objects.update_or_create(
                user=user,
                defaults={
                    "primary_character": character,
                    "nickname": user.username,
                },
            )
        return character

    def _stint(self, character, start):
        self.history_id += 1
        EveCharacterCorporationHistory.objects.create(
            character=character,
            record_id=self.history_id,
            corporation_id=CORP_ID,
            start_date=start,
        )

    def _fleet(self, instance_id, created_by, start, description):
        fleet = EveFleet.objects.create(
            start_time=start,
            type="training",
            created_by=created_by,
            description=description,
        )
        return EveFleetInstance.objects.create(id=instance_id, eve_fleet=fleet)

    def _kill(self, killmail_id, attackers, when):
        killmail = EveCharacterKillmail.objects.create(
            id=killmail_id,
            killmail_id=killmail_id,
            killmail_hash=f"hash-{killmail_id}",
            killmail_time=when,
            solar_system_id=1,
            ship_type_id=self.types["battleship"],
            attackers="[]",
            items="[]",
            character=attackers[0],
        )
        for attacker in attackers:
            EveCharacterKillmailAttacker.objects.create(
                killmail=killmail, character_id=attacker.character_id
            )

    def _attend(self, character, instance, ship_type_id, when):
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=character.character_id,
            character_name=character.character_name,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=ship_type_id,
            ship_name="Hull",
            solar_system_id=1,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(pk=member.pk).update(
            join_time=when
        )
        return member
