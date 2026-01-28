from django.test import Client

from app.test import TestCase

from fittings.models import EveFitting, EveDoctrine


class FittingsRouterTestCase(TestCase):
    """Test cases for the fittings router."""

    def setUp(self):
        self.client = Client()

        super().setUp()

    def test_get_doctrines(self):
        EveDoctrine.objects.create(
            name="Test Doctrine",
            type="non_strategic",
            description="A test doctrine",
        )

        response = self.client.get(
            "/api/doctrines/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        doctrines = response.json()
        self.assertEqual(1, len(doctrines))
        self.assertEqual("non_strategic", doctrines[0]["type"])

    def test_get_doctrine_by_id(self):
        doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type="strategic",
            description="A test doctrine",
        )

        response = self.client.get(
            f"/api/doctrines/{doctrine.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        doctrine_data = response.json()
        self.assertEqual("Test Doctrine", doctrine_data["name"])
        self.assertEqual("strategic", doctrine_data["type"])

    def test_get_doctrine_not_found(self):
        response = self.client.get(
            "/api/doctrines/99999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(404, response.status_code)

    def test_get_fittings(self):
        response = self.client.get(
            "/api/fittings/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fittings = response.json()
        self.assertEqual(0, len(fittings))

        fitting = EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
        )

        response = self.client.get(
            "/api/fittings/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fittings = response.json()
        self.assertEqual(1, len(fittings))

        response = self.client.get(
            f"/api/fittings/{fitting.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fitting = response.json()
        self.assertEqual("[ADV-5] Retribution", fitting["name"])
