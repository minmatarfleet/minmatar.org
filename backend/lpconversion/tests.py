from django.test import Client

# from django.contrib.auth.models import User, Permission

from app.test import TestCase

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

    # def test_create_order_api(self):
    #     perm = Permission.objects.get(name="lpconversion.add_lpsellorder")
    #     user = User.objects.create(
    #         username="Test User",
    #     )
    #     user.user_permissions.add([perm])
    #     user.save()
    #     self.client.force_login(user)

    #     request = '{"loyalty_points": 1000000}'

    #     response = self.client.post(BASE_URL, request, content_type="application/json",
    #                                 HTTP_AUTHORIZATION=f"Bearer {self.token}")

    #     print(response)
    #     self.assertEqual(response.status_code, 200)
