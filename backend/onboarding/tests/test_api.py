"""Tests for onboarding API endpoints."""

import uuid

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase

from onboarding.models import (
    OnboardingProgram,
    OnboardingProgramType,
    UserOnboardingAcknowledgment,
)
from users.helpers import add_user_permission

BASE = "/api/onboarding"
SRP = OnboardingProgramType.SRP
SRP_PROGRAMS = "/api/srp/programs"


def _make_token(user: User) -> str:
    payload = {"user_id": user.pk}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


class OnboardingApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="onboarder",
            password="unused",
        )
        self.token = _make_token(self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_get_unknown_program_type_returns_404(self):
        r = self.client.get(
            f"{BASE}/nope",
            **self.auth,
        )
        self.assertEqual(r.status_code, 404)
        self.assertIn("detail", r.json())

    def test_get_srp_without_ack_returns_not_current(self):
        r = self.client.get(f"{BASE}/{SRP}", **self.auth)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["program_type"], SRP)
        self.assertIn("current_version", data)
        self.assertIsNone(data["acknowledged_version"])
        self.assertFalse(data["is_current"])

    def test_post_ack_then_get_is_current(self):
        r_post = self.client.post(
            f"{BASE}/{SRP}/ack",
            **self.auth,
            content_type="application/json",
            data="{}",
        )
        self.assertEqual(r_post.status_code, 204)

        program = OnboardingProgram.objects.get(pk=SRP)
        r_get = self.client.get(f"{BASE}/{SRP}", **self.auth)
        self.assertEqual(r_get.status_code, 200)
        data = r_get.json()
        self.assertEqual(data["acknowledged_version"], str(program.version))
        self.assertTrue(data["is_current"])

    def test_version_bump_makes_stale(self):
        program = OnboardingProgram.objects.get(pk=SRP)
        UserOnboardingAcknowledgment.objects.create(
            user=self.user,
            program=program,
            acknowledged_version=program.version,
        )
        program.version = uuid.uuid4()
        program.save(update_fields=["version"])

        r = self.client.get(f"{BASE}/{SRP}", **self.auth)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertNotEqual(
            data["acknowledged_version"],
            data["current_version"],
        )
        self.assertFalse(data["is_current"])

    def test_post_ack_unknown_program_type_returns_404(self):
        r = self.client.post(
            f"{BASE}/missing/ack",
            **self.auth,
            content_type="application/json",
            data="{}",
        )
        self.assertEqual(r.status_code, 404)

    def test_srp_programs_forbidden_without_onboarding_ack(self):
        other = User.objects.create_user(username="no_ack", password="unused")
        token = _make_token(other)
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        add_user_permission(other, "view_evefleetshipreimbursement")
        r = self.client.get(SRP_PROGRAMS, **auth)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["detail"], "srp_onboarding_required")

    def test_srp_programs_ok_for_processor_without_personal_ack(self):
        processor = User.objects.create_user(
            username="processor", password="unused"
        )
        token = _make_token(processor)
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        add_user_permission(processor, "view_evefleetshipreimbursement")
        add_user_permission(processor, "change_evefleetshipreimbursement")
        r = self.client.get(SRP_PROGRAMS, **auth)
        self.assertEqual(r.status_code, 200)

    def test_srp_programs_forbidden_for_superuser_without_ack(self):
        admin = User.objects.create_user(
            username="super_no_ack",
            password="unused",
            is_superuser=True,
        )
        token = _make_token(admin)
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        add_user_permission(admin, "view_evefleetshipreimbursement")
        r = self.client.get(SRP_PROGRAMS, **auth)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["detail"], "srp_onboarding_required")
