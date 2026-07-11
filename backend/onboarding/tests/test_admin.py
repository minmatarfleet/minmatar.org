from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse

from app.test import TestCase
from onboarding.admin_views import (
    onboarding_home_view,
    onboarding_program_hub_view,
)
from onboarding.models import OnboardingProgram, OnboardingProgramType


class OnboardingAdminCustomizationsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="onboarding-viewer",
            password="test-pass",
            is_staff=True,
            is_superuser=False,
        )
        self.view_perm = Permission.objects.get(
            codename="view_onboardingprogram",
            content_type=ContentType.objects.get(
                app_label="onboarding", model="onboardingprogram"
            ),
        )
        self.program, _ = OnboardingProgram.objects.get_or_create(
            program_type=OnboardingProgramType.SRP,
        )

    def test_home_view_requires_permission(self):
        request = self.factory.get(reverse("admin:onboarding_home"))
        request.user = self.staff
        with self.assertRaises(PermissionDenied):
            onboarding_home_view(request)

        self.staff.user_permissions.add(self.view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request.user = self.staff
        response = onboarding_home_view(request)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "SRP")

    def test_program_hub_shows_acknowledgments(self):
        self.staff.user_permissions.add(self.view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request = self.factory.get(
            reverse(
                "admin:onboarding_program_hub",
                args=[OnboardingProgramType.SRP],
            )
        )
        request.user = self.staff
        response = onboarding_program_hub_view(
            request, OnboardingProgramType.SRP
        )
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "View acknowledgments")

    def test_get_app_list_shows_single_onboarding_link_in_system(self):
        self.staff.is_superuser = True
        self.staff.save(update_fields=["is_superuser"])
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request = self.factory.get("/admin/")
        request.user = self.staff
        app_list = admin.site.get_app_list(request)
        system_app = next(app for app in app_list if app["name"] == "System")
        model_names = {m["name"].lower() for m in system_app["models"]}
        self.assertIn("onboarding", model_names)
        self.assertNotIn("onboarding programs", model_names)
        self.assertNotIn("user onboarding acknowledgments", model_names)
