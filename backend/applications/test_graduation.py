"""Academy graduation pipeline: the bar, routing, the pipeline and reviews."""

from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.db.models import signals
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from applications import graduation
from applications.models import AcademyGraduationReview
from discord.models import DiscordChannelActivityRecord
from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.helpers.characters import set_primary_character
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCorporation,
    EvePlayer,
)
from groups.helpers import PEOPLE_TEAM

BASE_URL = "/api/eveonline/corporations/"
ACADEMY_ID = 98741376


def activity(**fields) -> graduation.PilotActivity:
    base = {
        "user_id": 1,
        "username": "pilot",
        "character_id": 1,
        "character_name": "Pilot",
        "prime_time": "US",
        "joined_at": None,
        "join_estimated": False,
        "skill_points": 20_000_000,
    }
    base.update(fields)
    return graduation.PilotActivity(**base)


class GraduationBarTestCase(TestCase):
    def test_needs_six_months(self):
        self.assertFalse(graduation.meets_bar(activity(fleets_90d=20), 179))
        self.assertTrue(graduation.meets_bar(activity(fleets_90d=4), 180))

    def test_any_one_line_of_the_bar(self):
        self.assertTrue(graduation.meets_bar(activity(kills_90d=8), 200))
        self.assertTrue(
            graduation.meets_bar(
                activity(voice_hours_90d=10, kills_90d=3), 200
            )
        )
        self.assertTrue(
            graduation.meets_bar(
                activity(skill_points=80_000_000, kills_90d=1), 200
            )
        )
        self.assertFalse(
            graduation.meets_bar(
                activity(fleets_90d=3, kills_90d=7, voice_hours_90d=9), 200
            )
        )


class GraduationRoutingTestCase(TestCase):
    def test_eu_goes_to_fosfo(self):
        picks = graduation.suggest_corporations(
            activity(prime_time="EU", kills_90d=20, small_gang_kills=20)
        )
        self.assertEqual(("FOSFO", "eu_skirmish"), picks[0])

    def test_large_gang_killer_goes_to_a_rat_not_tdt(self):
        picks = graduation.suggest_corporations(
            activity(
                skill_points=39_000_000,
                fleets_90d=8,
                kills_90d=161,
                kills_30d=68,
                small_gang_kills=7,
                medium_gang_kills=44,
                large_gang_kills=110,
            )
        )
        self.assertEqual(
            [("A-RAT", "large_gang"), ("SLTAR", "fleet_regular")], picks
        )

    def test_us_skirmisher_goes_to_tdt(self):
        picks = graduation.suggest_corporations(
            activity(
                skill_points=60_000_000,
                kills_90d=120,
                kills_30d=40,
                small_gang_kills=100,
                large_gang_kills=20,
            )
        )
        self.assertEqual(("TDT", "killboard"), picks[0])

    def test_building_pilot_goes_to_sltar(self):
        picks = graduation.suggest_corporations(
            activity(skill_points=12_000_000, fleets_90d=4)
        )
        self.assertEqual([("SLTAR", "building")], picks)


class GraduationEndpointTestCase(TestCase):
    def setUp(self):
        cache.clear()
        for sender, uid in (
            (EveCharacter, "populate_eve_character_public_data"),
            (EveCharacter, "populate_eve_character_private_data"),
            (EveAlliance, "eve_alliance_post_save"),
        ):
            signals.post_save.disconnect(sender=sender, dispatch_uid=uid)
        super().setUp()
        self.client = Client()
        self.alliance = EveAlliance.objects.create(
            alliance_id=MINMATAR_FLEET_ALLIANCE_ID, name="Minmatar Fleet"
        )
        self.academy = EveCorporation.objects.create(
            corporation_id=ACADEMY_ID,
            name="Minmatar Fleet Academy",
            ticker="L3ARN",
            alliance=self.alliance,
        )
        self.rattini = EveCorporation.objects.create(
            corporation_id=98726134,
            name="Rattini Tribe",
            ticker="A-RAT",
            alliance=self.alliance,
        )
        self.soltech = EveCorporation.objects.create(
            corporation_id=98647659,
            name="Soltech Armada",
            ticker="SLTAR",
            alliance=self.alliance,
        )
        self.other = EveCorporation.objects.create(
            corporation_id=12345, name="Other Corp", ticker="OTHER"
        )

    def _pilot(self, name, character_id, joined_days_ago, prime_time="US"):
        user = User.objects.create(username=name.lower().replace(" ", "_"))
        character = EveCharacter.objects.create(
            character_id=character_id,
            character_name=name,
            corporation_id=ACADEMY_ID,
            user=user,
        )
        set_primary_character(user, character)
        EvePlayer.objects.filter(user=user).update(prime_time=prime_time)
        EveCharacterCorporationHistory.objects.create(
            character=character,
            record_id=1,
            corporation_id=ACADEMY_ID,
            start_date=timezone.now() - timedelta(days=joined_days_ago),
        )
        return user, character

    def _kill(self, character, killmail_id, attackers, days_ago=5):
        mail = EveCharacterKillmail.objects.create(
            id=killmail_id,
            killmail_id=killmail_id,
            killmail_hash="hash",
            killmail_time=timezone.now() - timedelta(days=days_ago),
            solar_system_id=30002537,
            ship_type_id=587,
            victim_character_id=999,
            attackers="[]",
            items="[]",
            character=character,
        )
        EveCharacterKillmailAttacker.objects.create(
            killmail=mail, character_id=character.character_id
        )
        for n in range(attackers - 1):
            EveCharacterKillmailAttacker.objects.create(
                killmail=mail, character_id=500000 + n
            )

    def _get(self, corporation_id=ACADEMY_ID, token=None):
        return self.client.get(
            f"{BASE_URL}corporations/{corporation_id}/graduation",
            HTTP_AUTHORIZATION=f"Bearer {token or self.token}",
        )

    def _post(self, body, token=None):
        return self.client.post(
            f"{BASE_URL}corporations/{ACADEMY_ID}/graduation/reviews",
            body,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token or self.token}",
        )

    def test_only_the_academy_has_a_pipeline(self):
        self.make_superuser()
        self.assertEqual(404, self._get(self.other.corporation_id).status_code)
        self.assertEqual(200, self._get().status_code)

    def test_members_cannot_see_it(self):
        self.assertEqual(403, self._get().status_code)
        access = self.client.get(
            f"{BASE_URL}corporations/{ACADEMY_ID}/members/access",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        self.assertFalse(access["can_view_graduation"])

    def test_people_team_sees_and_reviews(self):
        patcher = patch(
            "eveonline.helpers.corporations.permissions.user_in_team",
            side_effect=lambda user, team: team == PEOPLE_TEAM,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        body = self._get().json()
        self.assertTrue(body["can_review"])
        access = self.client.get(
            f"{BASE_URL}corporations/{ACADEMY_ID}/members/access",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        self.assertTrue(access["can_view_graduation"])

    def test_pipeline_places_pilots(self):
        self.make_superuser()
        _, veteran = self._pilot("Big Pilot", 2001, 246)
        for n in range(10):
            self._kill(veteran, 9000 + n, attackers=30)
        self._pilot("New Pilot", 2002, 30)
        DiscordChannelActivityRecord.objects.create(
            username="big_pilot", activity_type="voice_minute", quantity=720
        )

        body = self._get().json()
        pilots = {pilot["character_name"]: pilot for pilot in body["pilots"]}
        big = pilots["Big Pilot"]
        self.assertEqual("due", big["stage"])
        self.assertEqual(246, big["days_in_academy"])
        self.assertEqual(10, big["kills_90d"])
        self.assertEqual(10, big["large_gang_kills"])
        self.assertEqual(12, big["voice_hours_90d"])
        self.assertTrue(big["ready"])
        self.assertEqual("A-RAT", big["suggestions"][0]["ticker"])
        self.assertEqual(98726134, big["suggestions"][0]["corporation_id"])
        self.assertEqual("training", pilots["New Pilot"]["stage"])
        self.assertFalse(pilots["New Pilot"]["ready"])
        # The review queue comes first.
        self.assertEqual("Big Pilot", body["pilots"][0]["character_name"])
        self.assertEqual(
            {"A-RAT", "SLTAR"}, {c["ticker"] for c in body["corporations"]}
        )

    def test_review_moves_the_pilot(self):
        self.make_superuser()
        user, character = self._pilot("Big Pilot", 2001, 200)

        missing_corp = self._post(
            {"character_id": 2001, "decision": "graduate"}
        )
        self.assertEqual(400, missing_corp.status_code)
        not_ours = self._post(
            {
                "character_id": 2001,
                "decision": "graduate",
                "corporation_ids": [self.other.corporation_id],
            }
        )
        self.assertEqual(400, not_ours.status_code)
        unknown = self._post({"character_id": 7, "decision": "keep"})
        self.assertEqual(400, unknown.status_code)

        kept = self._post(
            {"character_id": 2001, "decision": "keep", "note": " Talk again "}
        )
        self.assertEqual(201, kept.status_code)
        self.assertEqual("Talk again", kept.json()["note"])
        stage = self._get().json()["pilots"][0]
        self.assertEqual("kept", stage["stage"])
        self.assertEqual("keep", stage["last_review"]["decision"])

        graduated = self._post(
            {
                "character_id": 2001,
                "decision": "graduate",
                "corporation_ids": [98726134, 98726134, 98647659],
            }
        )
        self.assertEqual(201, graduated.status_code)
        self.assertEqual(
            [98726134, 98647659], graduated.json()["corporation_ids"]
        )
        review = AcademyGraduationReview.objects.filter(user=user).first()
        self.assertEqual(self.user, review.reviewed_by)
        self.assertEqual(character.character_id, review.character_id)
        self.assertEqual(
            "graduating", self._get().json()["pilots"][0]["stage"]
        )

    def test_only_reviewers_record_decisions(self):
        self._pilot("Big Pilot", 2001, 200)
        response = self._post({"character_id": 2001, "decision": "keep"})
        self.assertEqual(403, response.status_code)

    def test_recent_graduates(self):
        self.make_superuser()
        user = User.objects.create(username="graduate")
        character = EveCharacter.objects.create(
            character_id=3001,
            character_name="Grad Pilot",
            corporation_id=self.rattini.corporation_id,
            user=user,
        )
        set_primary_character(user, character)
        now = timezone.now()
        EveCharacterCorporationHistory.objects.create(
            character=character,
            record_id=1,
            corporation_id=ACADEMY_ID,
            start_date=now - timedelta(days=330),
        )
        EveCharacterCorporationHistory.objects.create(
            character=character,
            record_id=2,
            corporation_id=self.rattini.corporation_id,
            start_date=now - timedelta(days=9),
        )
        graduates = self._get().json()["graduates"]
        self.assertEqual(1, len(graduates))
        self.assertEqual("A-RAT", graduates[0]["ticker"])
        self.assertEqual(321, graduates[0]["days_in_academy"])
