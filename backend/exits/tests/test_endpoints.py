import json

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import auth_headers
from applications.models import EveCorporationApplication
from eveonline.models import EveCharacter, EveCorporation
from exits.helpers.answers import answer
from exits.models import Departure, RejoinFlag

BASE = "/api/exits/corporations/98000001/departures"


class DepartureEndpointsTest(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.ceo = User.objects.create(username="ceo")
        ceo_character = EveCharacter.objects.create(
            character_id=2112000001, character_name="Ceo", user=self.ceo
        )
        self.director = User.objects.create(username="director")
        director_character = EveCharacter.objects.create(
            character_id=2112000002,
            character_name="Director",
            user=self.director,
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Example Corp",
            track_exits=True,
            ceo=ceo_character,
        )
        self.corporation.directors.add(director_character)
        EveCorporation.objects.create(
            corporation_id=1000167, name="Pator Tech School"
        )
        EveCharacter.objects.create(
            character_id=7, character_name="Arkan Veld"
        )
        now = timezone.now()
        self.open = Departure.objects.create(
            corporation=self.corporation,
            character_id=7,
            first_missing_at=now,
            status="confirmed",
            confirmed_at=now,
            kind="exit",
            destination_corporation_id=1000167,
            destination_is_npc=True,
        )
        self.answered = Departure.objects.create(
            corporation=self.corporation,
            character_id=8,
            first_missing_at=now,
            status="confirmed",
            confirmed_at=now,
            kind="exit",
            reason="left",
        )

    def _get(self, user, query=""):
        return self.client.get(f"{BASE}{query}", **auth_headers(user))

    def test_ceo_lists_open_departures(self):
        response = self._get(self.ceo)
        self.assertEqual(response.status_code, 200)
        [row] = response.json()
        self.assertEqual(row["departure_ids"], [self.open.pk])
        self.assertEqual(row["character_name"], "Arkan Veld")
        self.assertEqual(row["destination_name"], "Pator Tech School")
        self.assertTrue(row["destination_is_npc"])
        self.assertFalse(row["registered"])
        self.assertEqual(len(self._get(self.ceo, "?state=answered").json()), 1)
        self.assertEqual(len(self._get(self.ceo, "?state=all").json()), 2)

    def test_director_gets_403(self):
        self.assertEqual(self._get(self.director).status_code, 403)

    def test_answers_endpoint_returns_groups(self):
        response = self.client.post(
            f"{BASE}/answers",
            data=json.dumps(
                {
                    "departure_ids": [self.open.pk],
                    "reason": "kicked_other",
                    "can_rejoin": False,
                    "note": "Awoxed a corp Orca",
                }
            ),
            content_type="application/json",
            **auth_headers(self.ceo),
        )
        self.assertEqual(response.status_code, 200)
        [row] = response.json()
        self.assertEqual(row["reason"], "kicked_other")
        flag = RejoinFlag.objects.get()
        self.assertEqual(row["flag_id"], flag.pk)

        response = self.client.post(
            f"/api/exits/flags/{flag.pk}/clear", **auth_headers(self.ceo)
        )
        self.assertEqual(response.status_code, 200)
        flag.refresh_from_db()
        self.assertIsNotNone(flag.cleared_at)

    def test_bad_answer_returns_its_status(self):
        response = self.client.post(
            f"{BASE}/answers",
            data=json.dumps(
                {
                    "departure_ids": [self.open.pk],
                    "reason": "kicked_other",
                    "can_rejoin": None,
                    "note": "",
                }
            ),
            content_type="application/json",
            **auth_headers(self.ceo),
        )
        self.assertEqual(response.status_code, 400)

    def test_can_view_departures_only_for_ceo(self):
        url = (
            "/api/eveonline/corporations/corporations/98000001/members/access"
        )
        ceo = self.client.get(url, **auth_headers(self.ceo)).json()
        director = self.client.get(url, **auth_headers(self.director)).json()
        self.assertTrue(ceo["can_view_departures"])
        self.assertFalse(director["can_view_departures"])


class ApplicationHistoryEndpointTest(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        ceo = User.objects.create(username="old ceo")
        old_corp = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Example Corp",
            track_exits=True,
            ceo=EveCharacter.objects.create(
                character_id=2112000001, character_name="Arkan Veld", user=ceo
            ),
        )
        self.applicant = User.objects.create(username="applicant")
        EveCharacter.objects.create(
            character_id=31, character_name="Dren Halvik", user=self.applicant
        )
        now = timezone.now()
        departure = Departure.objects.create(
            corporation=old_corp,
            character_id=31,
            user=self.applicant,
            first_missing_at=now,
            status="confirmed",
            confirmed_at=now,
            kind="exit",
        )
        answer(
            ceo,
            old_corp,
            [departure.pk],
            reason="kicked_other",
            can_rejoin=False,
            note="Awoxed",
        )

        self.recruiter = User.objects.create(username="recruiter")
        recruiter_character = EveCharacter.objects.create(
            character_id=32, character_name="Recruiter", user=self.recruiter
        )
        self.new_corp = EveCorporation.objects.create(
            corporation_id=98000002, name="Other Corp"
        )
        self.new_corp.recruiters.add(recruiter_character)
        self.other_recruiter = User.objects.create(username="other recruiter")
        other_corp = EveCorporation.objects.create(
            corporation_id=98000003, name="Third Corp"
        )
        other_corp.recruiters.add(
            EveCharacter.objects.create(
                character_id=33,
                character_name="Other",
                user=self.other_recruiter,
            )
        )
        self.application = EveCorporationApplication.objects.create(
            corporation_id=98000002, user=self.applicant, status="pending"
        )
        self.url = f"/api/exits/applications/{self.application.pk}/history"

    def test_recruiter_sees_history(self):
        response = self.client.get(self.url, **auth_headers(self.recruiter))
        self.assertEqual(response.status_code, 200)
        [entry] = response.json()
        self.assertEqual(entry["corporation_name"], "Example Corp")
        self.assertEqual(entry["note"], "Awoxed")
        self.assertTrue(entry["flag_active"])
        self.assertEqual(entry["answered_by_name"], "Arkan Veld")

    def test_applicant_gets_403_for_history(self):
        response = self.client.get(self.url, **auth_headers(self.applicant))
        self.assertEqual(response.status_code, 403)

    def test_other_corporation_recruiter_gets_403(self):
        response = self.client.get(
            self.url, **auth_headers(self.other_recruiter)
        )
        self.assertEqual(response.status_code, 403)
