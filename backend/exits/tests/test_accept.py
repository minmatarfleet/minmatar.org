from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import auth_headers
from applications.models import EveCorporationApplication
from eveonline.models import EveCharacter, EveCorporation
from exits.helpers.answers import answer
from exits.models import Departure, FlagAcceptance, RejoinFlag


class AcceptFlaggedTest(TestCase):
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
        self.departure = Departure.objects.create(
            corporation=old_corp,
            character_id=31,
            user=self.applicant,
            first_missing_at=now,
            status="confirmed",
            confirmed_at=now,
            kind="exit",
        )
        self.old_ceo = ceo
        self.old_corp = old_corp
        self.recruiter = User.objects.create(username="recruiter")
        corporation = EveCorporation.objects.create(
            corporation_id=98000002, name="Other Corp"
        )
        corporation.recruiters.add(
            EveCharacter.objects.create(
                character_id=32,
                character_name="Recruiter",
                user=self.recruiter,
            )
        )
        self.application = EveCorporationApplication.objects.create(
            corporation_id=98000002, user=self.applicant, status="pending"
        )
        self.url = (
            f"/api/applications/corporations/98000002/applications/"
            f"{self.application.pk}/accept"
        )

    def _flag(self):
        answer(
            self.old_ceo,
            self.old_corp,
            [self.departure.pk],
            reason="kicked_other",
            can_rejoin=False,
            note="Awoxed",
        )

    def _accept(self, query=""):
        return self.client.post(
            f"{self.url}{query}", **auth_headers(self.recruiter)
        )

    def test_flagged_accept_needs_confirmation(self):
        self._flag()
        response = self._accept()
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["flags"][0]["corporation_name"], "Example Corp")
        self.assertEqual(body["flags"][0]["note"], "Awoxed")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "pending")

    def test_confirmed_accept_is_recorded(self):
        self._flag()
        response = self._accept("?confirm_flags=true")
        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "accepted")
        acceptance = FlagAcceptance.objects.get()
        self.assertEqual(acceptance.application, self.application)
        self.assertEqual(acceptance.accepted_by, self.recruiter)
        self.assertEqual(acceptance.flag_ids, [RejoinFlag.objects.get().pk])

    def test_unflagged_accept_unchanged(self):
        response = self._accept()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FlagAcceptance.objects.exists())
