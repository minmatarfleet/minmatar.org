"""Tests for industry admin customizations."""

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory

from app.test import TestCase as AppTestCase


class IndustryAdminAppListTestCase(AppTestCase):
    def test_get_app_list_with_app_label(self):
        """app_index passes app_label; patched get_app_list must accept it."""
        user = User.objects.create_superuser(
            username="admin_app_list",
            email="admin@example.com",
            password="password",
        )
        request = RequestFactory().get("/admin/auth/")
        request.user = user

        app_list = admin.site.get_app_list(request, app_label="auth")

        self.assertIsInstance(app_list, list)
