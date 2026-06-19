"""Tests for industry Celery tasks."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone

from app.test import TestCase
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType

from industry.models import (
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)
from industry.tasks import sync_industry_jobs_for_order_assignees
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
