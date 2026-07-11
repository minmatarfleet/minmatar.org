from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse

from app.test import TestCase
from tribes.admin_group_views import tribe_group_hub_view, tribes_view
from tribes.models import Tribe, TribeGroup


class TribesAdminCustomizationsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="tribes-viewer",
            password="test-pass",
            is_staff=True,
            is_superuser=False,
        )
        self.view_perm = Permission.objects.get(
            codename="view_tribegroup",
            content_type=ContentType.objects.get(
                app_label="tribes", model="tribegroup"
            ),
        )
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Dreads",
        )

    def test_tribes_view_requires_permission(self):
        request = self.factory.get(reverse("admin:tribes_home"))
        request.user = self.staff
        with self.assertRaises(PermissionDenied):
            tribes_view(request)

        self.staff.user_permissions.add(self.view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request.user = self.staff
        response = tribes_view(request)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Capitals")
        self.assertContains(response, "Dreads")

    def test_group_hub_view_shows_sections(self):
        self.staff.user_permissions.add(self.view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request = self.factory.get(
            reverse("admin:tribes_group_hub", args=[self.tribe_group.pk])
        )
        request.user = self.staff
        response = tribe_group_hub_view(request, self.tribe_group.pk)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Memberships")
        self.assertContains(response, "Activity records")

    def test_get_app_list_shows_single_tribes_link_in_community(self):
        self.staff.is_superuser = True
        self.staff.save(update_fields=["is_superuser"])
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request = self.factory.get("/admin/")
        request.user = self.staff
        app_list = admin.site.get_app_list(request)
        community_app = next(
            app for app in app_list if app["name"] == "Community"
        )
        model_names = {
            model["name"].lower() for model in community_app["models"]
        }
        self.assertIn("tribes", model_names)
