from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse

from app.test import TestCase
from fittings.models import EveFitting

from market.admin_location_views import (
    market_location_fitting_expectations_view,
    market_locations_view,
)
from market.models import EveMarketFittingExpectation
from market.tests.test_fitting_expectations import _make_eve_type
from market.tests.test_market_vision import _make_location


class MarketAdminPermissionsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.location = _make_location()
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="market-viewer",
            password="test-pass",
            is_staff=True,
            is_superuser=False,
        )
        self.locations_view_perm = Permission.objects.get(
            codename="view_evemarketitemexpectation",
            content_type=ContentType.objects.get(
                app_label="market", model="evemarketitemexpectation"
            ),
        )
        self.view_perm = Permission.objects.get(
            codename="view_evemarketfittingexpectation",
            content_type=ContentType.objects.get(
                app_label="market", model="evemarketfittingexpectation"
            ),
        )
        self.change_perm = Permission.objects.get(
            codename="change_evemarketfittingexpectation",
            content_type=ContentType.objects.get(
                app_label="market", model="evemarketfittingexpectation"
            ),
        )

    def test_locations_view_requires_market_view_permission(self):
        request = self.factory.get(reverse("admin:market_locations"))
        request.user = self.staff
        with self.assertRaises(PermissionDenied):
            market_locations_view(request)

        self.staff.user_permissions.add(self.locations_view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request.user = self.staff
        response = market_locations_view(request)
        self.assertEqual(200, response.status_code)

    def test_post_without_change_permission_is_denied(self):
        fitting_type = _make_eve_type(587, "Rifter")
        fitting = EveFitting.objects.create(
            name="[FL33T] Rifter",
            eft_format="[Rifter, [FL33T] Rifter]",
            ship_id=fitting_type.id,
        )
        self.staff.user_permissions.add(self.view_perm)
        url = reverse(
            "admin:market_location_fitting_expectations",
            args=[self.location.pk],
        )
        request = self.factory.post(url, {f"quantity_{fitting.pk}": "5"})
        request.user = self.staff
        with self.assertRaises(PermissionDenied):
            market_location_fitting_expectations_view(
                request, self.location.pk
            )

        self.assertFalse(
            EveMarketFittingExpectation.objects.filter(
                location=self.location, fitting=fitting
            ).exists()
        )
