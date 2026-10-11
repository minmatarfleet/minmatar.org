import json

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from surveys.constants import STATUS_OPEN
from surveys.models import (
    SurveyAnswer,
    SurveyCampaign,
    SurveyResponse,
)

BASE = "/api/surveys"


def _token(user):
    return jwt.encode(
        {"user_id": user.pk}, settings.SECRET_KEY, algorithm="HS256"
    )


def _auth(user):
    return {"HTTP_AUTHORIZATION": f"Bearer {_token(user)}"}


class SurveyRouterTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(username="pilot")
        self.manager = User.objects.create(username="exec", is_superuser=True)
        self.campaign = SurveyCampaign.objects.create(
            year=2027,
            quarter=1,
            definition_key="community",
            title="2027 Q1 Community Survey",
            status=STATUS_OPEN,
            opens_at=timezone.now(),
        )

    # ---- discovery / rendering ----
    def test_active_and_questions(self):
        r = self.client.get(f"{BASE}/active", **_auth(self.user))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["campaign"]["id"], self.campaign.pk)
        self.assertFalse(r.json()["has_responded"])

        r = self.client.get(
            f"{BASE}/{self.campaign.pk}/questions", **_auth(self.user)
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        member_keys = {
            q["key"] for b in body["member_blocks"] for q in b["questions"]
        }
        self.assertIn("core.satisfaction", member_keys)

    def test_context_autofills_without_error(self):
        r = self.client.get(
            f"{BASE}/{self.campaign.pk}/context", **_auth(self.user)
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("tenure_cohort", r.json())

    # ---- submission + idempotency ----
    def test_submit_is_idempotent(self):
        payload = {
            "answers": [
                {"question_key": "core.satisfaction", "value": 4},
                {"question_key": "core.enps", "value": 9},
                {"question_key": "core.leave_reason", "value": "nothing"},
            ],
            "context_corrections": {"prime_time": "EU"},
        }
        for _ in range(2):
            r = self.client.post(
                f"{BASE}/{self.campaign.pk}/responses",
                data=json.dumps(payload),
                content_type="application/json",
                **_auth(self.user),
            )
            self.assertEqual(r.status_code, 200, r.content)
        # Only one response, answers de-duplicated by (response, question_key).
        self.assertEqual(
            SurveyResponse.objects.filter(campaign=self.campaign).count(), 1
        )
        resp = SurveyResponse.objects.get(
            campaign=self.campaign, user=self.user
        )
        self.assertEqual(resp.prime_time, "EU")  # local correction snapshotted
        self.assertEqual(
            SurveyAnswer.objects.filter(
                response=resp, question_key="core.satisfaction"
            ).count(),
            1,
        )
        sat = SurveyAnswer.objects.get(
            response=resp, question_key="core.satisfaction"
        )
        self.assertEqual(sat.numeric_value, 4.0)

    def test_get_my_response_reads_back_answers(self):
        # Nothing submitted yet.
        r = self.client.get(
            f"{BASE}/{self.campaign.pk}/response", **_auth(self.user)
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()["has_responded"])
        self.assertEqual(r.json()["answers"], {})

        self.client.post(
            f"{BASE}/{self.campaign.pk}/responses",
            data=json.dumps(
                {
                    "answers": [
                        {"question_key": "core.satisfaction", "value": 4},
                        {
                            "question_key": "core.leave_reason",
                            "value": "burnout",
                        },
                    ]
                }
            ),
            content_type="application/json",
            **_auth(self.user),
        )
        r = self.client.get(
            f"{BASE}/{self.campaign.pk}/response", **_auth(self.user)
        )
        body = r.json()
        self.assertTrue(body["has_responded"])
        # Numeric read back as a whole number, text as its string.
        self.assertEqual(body["answers"]["core.satisfaction"], 4)
        self.assertEqual(body["answers"]["core.leave_reason"], "burnout")

    def test_editing_clears_emptied_answers(self):
        resp = SurveyResponse.objects.create(
            campaign=self.campaign, user=self.user
        )
        SurveyAnswer.objects.create(
            response=resp,
            question_key="core.leave_reason",
            text_value="burnout",
        )
        # Re-submit with the field explicitly emptied → the answer is removed.
        self.client.post(
            f"{BASE}/{self.campaign.pk}/responses",
            data=json.dumps(
                {
                    "answers": [
                        {"question_key": "core.leave_reason", "value": None}
                    ]
                }
            ),
            content_type="application/json",
            **_auth(self.user),
        )
        self.assertFalse(
            SurveyAnswer.objects.filter(
                response=resp, question_key="core.leave_reason"
            ).exists()
        )

    def test_submit_ignores_unknown_questions(self):
        payload = {
            "answers": [{"question_key": "not.a.real.key", "value": "secret"}]
        }
        self.client.post(
            f"{BASE}/{self.campaign.pk}/responses",
            data=json.dumps(payload),
            content_type="application/json",
            **_auth(self.user),
        )
        self.assertFalse(
            SurveyAnswer.objects.filter(question_key="not.a.real.key").exists()
        )

    # ---- permission gating ----
    def test_manage_requires_permission(self):
        r = self.client.get(f"{BASE}/", **_auth(self.user))
        self.assertEqual(r.status_code, 403)
        r = self.client.get(f"{BASE}/", **_auth(self.manager))
        self.assertEqual(r.status_code, 200)

    def test_close_triggers_aggregates(self):
        self.client.post(
            f"{BASE}/{self.campaign.pk}/responses",
            data=json.dumps(
                {
                    "answers": [
                        {"question_key": "core.satisfaction", "value": 5}
                    ]
                }
            ),
            content_type="application/json",
            **_auth(self.user),
        )
        r = self.client.patch(
            f"{BASE}/{self.campaign.pk}",
            data=json.dumps({"status": "closed"}),
            content_type="application/json",
            **_auth(self.manager),
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.campaign.aggregates.exists())
        agg = self.campaign.aggregates.get(
            question_key="core.satisfaction", segment_key="all"
        )
        self.assertEqual(agg.mean, 5.0)
        self.assertEqual(agg.n, 1)

    def test_corp_report_scope_and_suppression(self):
        # Seed one corp response directly (bypasses autofill snapshotting).
        resp = SurveyResponse.objects.create(
            campaign=self.campaign,
            user=User.objects.create(username="corpmate"),
            corporation_name="A-RAT",
        )
        SurveyAnswer.objects.create(
            response=resp, question_key="corp.connection", numeric_value=5
        )

        # Non-manager, non-officer is forbidden.
        r = self.client.get(
            f"{BASE}/{self.campaign.pk}/corp-report", **_auth(self.user)
        )
        self.assertEqual(r.status_code, 403)

        # Manager sees alliance-wide; the small corp is suppressed (n < min_n).
        r = self.client.get(
            f"{BASE}/{self.campaign.pk}/corp-report", **_auth(self.manager)
        )
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body["scope"], "all")
        arat = next(c for c in body["corps"] if c["corp"] == "A-RAT")
        self.assertEqual(arat["n"], 1)
        self.assertTrue(arat["suppressed"])
        conn = next(
            q
            for q in arat["questions"]
            if q["question_key"] == "corp.connection"
        )
        self.assertIsNone(conn["mean"])  # hidden while suppressed

    def test_results_route_resolves(self):
        r = self.client.get(
            f"{BASE}/{self.campaign.pk}/results?segment=all",
            **_auth(self.manager),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("aggregates", r.json())
