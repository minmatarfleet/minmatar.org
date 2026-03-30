"""Tests for blueprint list endpoints (q query param filters by type name)."""

from django.test import Client

from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveCharacterBlueprint
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase as AppTestCase


class BlueprintsEndpointTestCase(AppTestCase):
    """GET /api/industry/blueprints and copies: empty without q; filter with q."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eve_category, _ = EveCategory.objects.get_or_create(
            id=1, defaults={"name": "Test Category", "published": True}
        )
        cls.eve_group, _ = EveGroup.objects.get_or_create(
            id=1,
            defaults={
                "name": "Test Group",
                "published": True,
                "eve_category": cls.eve_category,
            },
        )

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.character = EveCharacter.objects.get_or_create(
            character_id=999001,
            defaults={"character_name": "Test Char", "user": self.user},
        )[0]
        set_primary_character(self.user, self.character)
        self.eve_type_match = EveType.objects.create(
            id=999301,
            name="Raven Caldari Battleship Blueprint",
            published=True,
            eve_group=self.eve_group,
        )
        self.eve_type_other = EveType.objects.create(
            id=999302,
            name="Some Other Type Blueprint",
            published=True,
            eve_group=self.eve_group,
        )

    def test_originals_empty_without_q(self):
        response = self.client.get("/api/industry/blueprints/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_originals_whitespace_q_returns_empty(self):
        response = self.client.get("/api/industry/blueprints/?q=   ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_originals_filters_by_type_name(self):
        EveCharacterBlueprint.objects.create(
            item_id=9001,
            character=self.character,
            type_id=self.eve_type_match.id,
            location_id=1,
            location_flag="Hangar",
            material_efficiency=0,
            time_efficiency=0,
            quantity=-1,
            runs=-1,
        )
        EveCharacterBlueprint.objects.create(
            item_id=9002,
            character=self.character,
            type_id=self.eve_type_other.id,
            location_id=1,
            location_flag="Hangar",
            material_efficiency=0,
            time_efficiency=0,
            quantity=-1,
            runs=-1,
        )
        response = self.client.get("/api/industry/blueprints/?q=raven")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["type_id"], self.eve_type_match.id)

    def test_copies_empty_without_q(self):
        response = self.client.get("/api/industry/blueprints/copies/copies")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_copies_filters_by_type_name(self):
        EveCharacterBlueprint.objects.create(
            item_id=9101,
            character=self.character,
            type_id=self.eve_type_match.id,
            location_id=1,
            location_flag="Hangar",
            material_efficiency=0,
            time_efficiency=0,
            quantity=1,
            runs=10,
        )
        EveCharacterBlueprint.objects.create(
            item_id=9102,
            character=self.character,
            type_id=self.eve_type_other.id,
            location_id=1,
            location_flag="Hangar",
            material_efficiency=0,
            time_efficiency=0,
            quantity=1,
            runs=10,
        )
        response = self.client.get(
            "/api/industry/blueprints/copies/copies?q=raven"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["type_id"], self.eve_type_match.id)
