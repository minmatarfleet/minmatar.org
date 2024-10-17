from datetime import datetime

from django.contrib.auth.models import Permission, User
from django.test import Client

from app.test import TestCase
from lpconversion.models import LpPrice, current_price

BASE_URL = "/api/conversion/orders"


class LpOrderTestCase(TestCase):
    """
    Unit tests for LP Conversion API.
    """

    def setUp(self):
        self.client = Client()

        super().setUp()

    def test_get_orders_api(self):
        response = self.client.get(
            BASE_URL, HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_current_price(self):
        LpPrice.objects.create(
            price=700,
            active_from=datetime.fromisoformat(
                "2019-01-01T10:00:00.000+00:00"
            ),
        )
        LpPrice.objects.create(
            price=650,
            active_from=datetime.fromisoformat(
                "2021-01-01T10:00:00.000+00:00"
            ),
        )
        LpPrice.objects.create(
            price=600,
            active_from=datetime.fromisoformat(
                "2020-01-01T10:00:00.000+00:00"
            ),
        )
        self.assertEqual(650, current_price())

    def test_create_order_api(self):
        user = User.objects.get(username="test")
        user.user_permissions.add(
            Permission.objects.get(codename="add_lpsellorder")
        )
        user.save()
        self.client.force_login(user)

        request = '{"loyalty_points": 1000000}'

        response = self.client.post(
            BASE_URL,
            request,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        print("Response=", response.content)
        self.assertEqual(response.status_code, 200)
