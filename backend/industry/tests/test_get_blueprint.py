"""Tests for GET /api/industry/blueprints/{item_id}."""

from datetime import timedelta

from django.test import Client
from django.utils import timezone

from eveonline.helpers.characters import set_primary_character
from eveonline.models import (
    EveCharacter,
    EveCharacterBlueprint,
    EveCharacterIndustryJob,
    EveCorporation,
    EveCorporationBlueprint,
    EveCorporationIndustryJob,
)
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase as AppTestCase


class GetBlueprintDetailTestCase(AppTestCase):
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
            character_id=888001,
            defaults={"character_name": "BP Owner", "user": self.user},
        )[0]
        set_primary_character(self.user, self.character)
        self.eve_type = EveType.objects.create(
            id=888101,
            name="Test Ship Blueprint",
            published=True,
            eve_group=self.eve_group,
        )

    def test_not_found(self):
        r = self.client.get("/api/industry/blueprints/999999999")
        self.assertEqual(r.status_code, 404)
        self.assertIn("detail", r.json())

    def test_character_blueprint_no_jobs(self):
        EveCharacterBlueprint.objects.create(
            item_id=88001,
            character=self.character,
            type_id=self.eve_type.id,
            location_id=1,
            location_flag="Hangar",
            material_efficiency=0,
            time_efficiency=0,
            quantity=-1,
            runs=-1,
        )
        r = self.client.get("/api/industry/blueprints/88001")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["item_id"], 88001)
        self.assertEqual(data["type_id"], self.eve_type.id)
        self.assertTrue(data["is_original"])
        self.assertEqual(data["current_jobs"], [])
        self.assertEqual(data["historical_jobs"], [])

    def test_jobs_split_current_and_historical(self):
        now = timezone.now()
        EveCharacterBlueprint.objects.create(
            item_id=88002,
            character=self.character,
            type_id=self.eve_type.id,
            location_id=1,
            location_flag="Hangar",
            material_efficiency=0,
            time_efficiency=0,
            quantity=1,
            runs=5,
        )
        EveCharacterIndustryJob.objects.create(
            job_id=1001,
            character=self.character,
            activity_id=1,
            blueprint_id=88002,
            blueprint_type_id=self.eve_type.id,
            blueprint_location_id=1,
            facility_id=2,
            location_id=3,
            output_location_id=4,
            status="active",
            installer_id=self.character.character_id,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            duration=7200,
            runs=1,
            licensed_runs=0,
        )
        EveCharacterIndustryJob.objects.create(
            job_id=1002,
            character=self.character,
            activity_id=1,
            blueprint_id=88002,
            blueprint_type_id=self.eve_type.id,
            blueprint_location_id=1,
            facility_id=2,
            location_id=3,
            output_location_id=4,
            status="delivered",
            installer_id=self.character.character_id,
            start_date=now - timedelta(days=2),
            end_date=now - timedelta(days=1),
            duration=3600,
            runs=1,
            licensed_runs=0,
            completed_date=now - timedelta(days=1),
        )
        r = self.client.get("/api/industry/blueprints/88002")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data["is_original"])
        self.assertEqual(len(data["current_jobs"]), 1)
        self.assertEqual(data["current_jobs"][0]["job_id"], 1001)
        self.assertEqual(data["current_jobs"][0]["status"], "active")
        self.assertEqual(data["current_jobs"][0]["source"], "character")
        self.assertEqual(len(data["historical_jobs"]), 1)
        self.assertEqual(data["historical_jobs"][0]["job_id"], 1002)
        self.assertEqual(data["historical_jobs"][0]["status"], "delivered")

    def test_corporation_blueprint_with_corp_job(self):
        corp = EveCorporation.objects.create(
            corporation_id=777001,
            name="Test Corp",
        )
        EveCorporationBlueprint.objects.create(
            item_id=88003,
            corporation=corp,
            type_id=self.eve_type.id,
            location_id=1,
            location_flag="CorpSAG",
            material_efficiency=0,
            time_efficiency=0,
            quantity=-1,
            runs=-1,
        )
        now = timezone.now()
        EveCorporationIndustryJob.objects.create(
            job_id=2001,
            corporation=corp,
            activity_id=1,
            blueprint_id=88003,
            blueprint_type_id=self.eve_type.id,
            blueprint_location_id=1,
            facility_id=2,
            location_id=3,
            output_location_id=4,
            status="ready",
            installer_id=self.character.character_id,
            start_date=now - timedelta(hours=2),
            end_date=now + timedelta(hours=2),
            duration=14400,
            runs=1,
            licensed_runs=0,
        )
        r = self.client.get("/api/industry/blueprints/88003")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["owner"]["entity_type"], "corporation")
        self.assertEqual(data["owner"]["entity_id"], 777001)
        self.assertEqual(len(data["current_jobs"]), 1)
        self.assertEqual(data["current_jobs"][0]["source"], "corporation")
        self.assertEqual(data["current_jobs"][0]["corporation_id"], 777001)
