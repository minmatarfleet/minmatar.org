import json
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone

from eveonline.models import EveCharacter, EveCorporation
from exits.models import Departure
from surveys.helpers import exit_tokens
from surveys.models import (
    ExitSurveyAnswer,
    ExitSurveyInvite,
    ExitSurveyResponse,
)

RATINGS = {
    "exit.enjoyment": 4,
    "exit.leadership": 3,
    "exit.activity": 2,
    "exit.welcome": 5,
}


class ExitSurveyEndpointTest(TestCase):
    def setUp(self):
        self.client = Client()
        now = timezone.now()
        corporation = EveCorporation.objects.create(
            corporation_id=98000001, name="Example Corp"
        )
        EveCorporation.objects.create(
            corporation_id=98000002, name="Tribal Liberation Force"
        )
        EveCharacter.objects.create(
            character_id=41, character_name="Kesh Varo"
        )
        self.departure = Departure.objects.create(
            corporation=corporation,
            character_id=41,
            first_missing_at=now - timedelta(days=3),
            status="confirmed",
            confirmed_at=now,
            kind="exit",
            destination_corporation_id=1000167,
            reason="left",
        )
        self.invite = ExitSurveyInvite.objects.create(
            departure=self.departure,
            character_id=41,
            definition_key="exit",
            definition_version=1,
            channel="eve_mail",
            status="sent",
            sent_at=now,
            expires_at=now + timedelta(days=30),
        )
        self.token = exit_tokens.mint(self.invite)
        self.url = f"/api/surveys/exit/{self.token}"

    def _post(self, answers):
        return self.client.post(
            self.url,
            data=json.dumps(
                {
                    "answers": [
                        {"question_key": k, "value": v}
                        for k, v in answers.items()
                    ]
                }
            ),
            content_type="application/json",
        )

    def test_form_for_valid_token(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["corporation_name"], "Example Corp")
        self.assertEqual(body["character_name"], "Kesh Varo")
        self.assertEqual(body["kind"], "exit")
        questions = [q for block in body["blocks"] for q in block["questions"]]
        self.assertEqual(
            questions[0]["label"],
            "Overall, how much did you enjoy Example Corp?",
        )
        self.assertTrue(all("{" not in q["label"] for q in questions))

    def test_alliance_move_names_the_new_corporation(self):
        self.departure.kind = "alliance_move"
        self.departure.destination_corporation_id = 98000002
        self.departure.save()
        self.invite.definition_key = "alliance_move"
        self.invite.save()
        body = self.client.get(self.url).json()
        self.assertEqual(
            body["new_corporation_name"], "Tribal Liberation Force"
        )
        labels = [q["label"] for b in body["blocks"] for q in b["questions"]]
        self.assertIn("Why did you move to Tribal Liberation Force?", labels)

    def test_bad_token_is_404(self):
        self.assertEqual(
            self.client.get("/api/surveys/exit/nonsense").status_code, 404
        )

    def test_used_token_is_410(self):
        self.assertEqual(self._post(RATINGS).status_code, 201)
        self.assertEqual(self.client.get(self.url).status_code, 410)

    def test_expired_token_is_410(self):
        with patch(
            "django.core.signing.time.time",
            return_value=timezone.now().timestamp() + 31 * 86400,
        ):
            self.assertEqual(self.client.get(self.url).status_code, 410)

    def test_submit_once(self):
        answers = dict(RATINGS)
        answers["exit.why_left"] = ["Timezone", "The corporation was inactive"]
        answers["exit.problem"] = "Nobody flew in my timezone"
        self.assertEqual(self._post(answers).status_code, 201)
        response = ExitSurveyResponse.objects.get()
        self.assertEqual(response.corporation_id, 98000001)
        self.assertEqual(response.definition_key, "exit")
        self.assertEqual(response.definition_version, 1)
        self.assertEqual(
            ExitSurveyAnswer.objects.get(
                question_key="exit.enjoyment"
            ).numeric_value,
            4,
        )
        self.assertEqual(
            ExitSurveyAnswer.objects.get(
                question_key="exit.why_left"
            ).json_value,
            ["Timezone", "The corporation was inactive"],
        )
        self.assertEqual(
            ExitSurveyAnswer.objects.get(
                question_key="exit.problem"
            ).text_value,
            "Nobody flew in my timezone",
        )
        self.invite.refresh_from_db()
        self.assertIsNotNone(self.invite.responded_at)
        self.assertEqual(self._post(RATINGS).status_code, 410)
        self.assertEqual(ExitSurveyResponse.objects.count(), 1)

    def test_missing_rating_is_400(self):
        answers = dict(RATINGS)
        del answers["exit.welcome"]
        response = self._post(answers)
        self.assertEqual(response.status_code, 400)
        self.assertIn("exit.welcome", response.json()["detail"])
        self.assertFalse(ExitSurveyResponse.objects.exists())

    def test_out_of_range_rating_is_400(self):
        answers = dict(RATINGS)
        answers["exit.enjoyment"] = 9
        self.assertEqual(self._post(answers).status_code, 400)

    def test_unknown_choice_is_dropped(self):
        answers = dict(RATINGS)
        answers["exit.why_left"] = ["Timezone", "<script>"]
        self.assertEqual(self._post(answers).status_code, 201)
        self.assertEqual(
            ExitSurveyAnswer.objects.get(
                question_key="exit.why_left"
            ).json_value,
            ["Timezone"],
        )
