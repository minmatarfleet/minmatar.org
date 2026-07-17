"""Tests for industry Celery tasks."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.utils import timezone

from app.test import TestCase
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType

from industry.helpers.cost_indices import sync_industry_system_cost_indices
from industry.helpers.facility_profiles import AMAMAKE_SYSTEM_ID
from industry.models import (
    IndustryOrderItem,
    IndustryOrderItemAssignment,
    IndustrySystemCostIndex,
)
from industry.tasks import (
    sync_industry_jobs_for_order_assignees,
    sync_industry_system_cost_indices_task,
)
from industry.test_utils import create_industry_order


class IndustryTasksTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category, _ = EveCategory.objects.get_or_create(
            id=9101,
            defaults={"name": "Category", "published": True},
        )
        cls.group, _ = EveGroup.objects.get_or_create(
            id=9101,
            defaults={
                "name": "Group",
                "published": True,
                "eve_category": cls.category,
            },
        )
        cls.eve_type, _ = EveType.objects.get_or_create(
            id=9101,
            defaults={
                "name": "Task Widget",
                "published": True,
                "eve_group": cls.group,
            },
        )

    @patch("industry.tasks.sync_industry_jobs_for_character.delay")
    def test_sync_industry_jobs_dedupes_characters_by_user(
        self, sync_delay_mock
    ):
        user = User.objects.create_user(username="industry_task_user")
        location = EveLocation.objects.create(
            location_id=91001,
            location_name="Industry Hub",
            solar_system_id=1,
            solar_system_name="Test",
        )
        primary = EveCharacter.objects.create(
            character_id=91001,
            character_name="Primary Pilot",
            user=user,
        )
        alt = EveCharacter.objects.create(
            character_id=91002,
            character_name="Alt Pilot",
            user=user,
        )
        set_primary_character(user, primary)

        needed_by = (timezone.now() + timedelta(days=7)).date()
        order = create_industry_order(
            needed_by=needed_by,
            character=primary,
            location=location,
        )
        item = IndustryOrderItem.objects.create(
            order=order,
            eve_type=self.eve_type,
            quantity=1,
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item,
            character=primary,
            quantity=1,
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item,
            character=alt,
            quantity=1,
        )

        sync_industry_jobs_for_order_assignees()

        scheduled_ids = {
            call.args[0] for call in sync_delay_mock.call_args_list
        }
        self.assertEqual({91001, 91002}, scheduled_ids)


class IndustryCostIndexSyncTestCase(TestCase):
    @patch("industry.helpers.cost_indices.esi_provider")
    def test_sync_upserts_manufacturing_and_reaction(self, esi_provider):
        IndustrySystemCostIndex.objects.create(
            solar_system_id=999,
            manufacturing=0.5,
            reaction=0.5,
        )
        esi_provider.client.Industry.GetIndustrySystems.return_value = (
            MagicMock(
                results=MagicMock(
                    return_value=[
                        {
                            "solar_system_id": AMAMAKE_SYSTEM_ID,
                            "cost_indices": [
                                {
                                    "activity": "manufacturing",
                                    "cost_index": 0.1238,
                                },
                                {
                                    "activity": "reaction",
                                    "cost_index": 0.1155,
                                },
                                {
                                    "activity": "researching_time_efficiency",
                                    "cost_index": 0.01,
                                },
                            ],
                        },
                        {
                            "solar_system_id": 30002059,
                            "cost_indices": [
                                {
                                    "activity": "manufacturing",
                                    "cost_index": 0.08,
                                },
                                {"activity": "reaction", "cost_index": 0.07},
                            ],
                        },
                    ]
                )
            )
        )

        count = sync_industry_system_cost_indices()
        self.assertEqual(count, 2)
        esi_provider.client.Industry.GetIndustrySystems.assert_called_once()
        esi_provider.client.Industry.GetIndustrySystems.return_value.results.assert_called_once_with(
            use_etag=False
        )

        self.assertFalse(
            IndustrySystemCostIndex.objects.filter(
                solar_system_id=999
            ).exists()
        )
        amamake = IndustrySystemCostIndex.objects.get(
            solar_system_id=AMAMAKE_SYSTEM_ID
        )
        self.assertAlmostEqual(amamake.manufacturing, 0.1238)
        self.assertAlmostEqual(amamake.reaction, 0.1155)
        auner = IndustrySystemCostIndex.objects.get(solar_system_id=30002059)
        self.assertAlmostEqual(auner.manufacturing, 0.08)
        self.assertAlmostEqual(auner.reaction, 0.07)

    @patch("industry.tasks.sync_industry_system_cost_indices")
    def test_celery_task_delegates_to_helper(self, sync_mock):
        sync_mock.return_value = 42
        self.assertEqual(sync_industry_system_cost_indices_task(), 42)
        sync_mock.assert_called_once()
