"""Tests for industry daily Discord summary message builder."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from app.test import TestCase as AppTestCase
from eveonline.models import EveCharacter, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType

from industry.models import IndustryOrderItem, IndustryOrderItemAssignment
from industry.test_utils import create_industry_order
from reminders.industry_daily_summary import (
    build_industry_daily_summary_message,
)


class IndustryDailySummaryMessageTests(AppTestCase):
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
        self.character = EveCharacter.objects.get_or_create(
            character_id=991001,
            defaults={"character_name": "Builder", "user": self.user},
        )[0]
        self.builder2 = EveCharacter.objects.create(
            character_id=991002,
            character_name="Builder Two",
            user=self.user,
        )
        self.eve_type = EveType.objects.create(
            id=991201,
            name="Test Widget",
            published=True,
            eve_group=self.eve_group,
        )
        self.location = EveLocation.objects.create(
            location_id=1999101,
            location_name="Test Station",
            solar_system_id=300001,
            solar_system_name="Test System",
            short_name="TST",
        )

    def test_empty_summary(self):
        text = build_industry_daily_summary_message()
        self.assertIn("# Industry order summary", text)
        self.assertIn("## Active orders", text)
        self.assertIn("Open builds, sorted by where they’re headed.", text)
        self.assertIn("## Unassigned order items", text)
        self.assertIn(
            "These order items still need someone to take the work.", text
        )
        self.assertIn("- *(none)*", text)
        self.assertIn("**Total order amount:** 0B", text)
        self.assertIn("**Total available margin:** 0B", text)

    def test_excludes_fulfilled_orders(self):
        create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            fulfilled_at=timezone.now(),
            location=self.location,
        )
        text = build_industry_daily_summary_message()
        self.assertIn("- *(none)*", text)

    def test_active_order_and_undelivered_assignment_totals(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        item = IndustryOrderItem.objects.create(
            order=order,
            eve_type=self.eve_type,
            quantity=10,
            target_unit_price=Decimal("1000000000"),
            target_estimated_margin=Decimal("50000000"),
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item,
            character=self.builder2,
            quantity=2,
        )
        text = build_industry_daily_summary_message()
        code = order.public_short_code
        self.assertIn(f"`{code}` [TST] Test Groups (0.5B profit)", text)
        self.assertIn(
            f"- `{code}` [TST] {self.eve_type.name} x8 (0.4B profit)",
            text,
        )
        self.assertIn("**Total order amount:** 2B", text)
        self.assertIn("**Total available margin:** 0.1B", text)

    def test_fully_assigned_in_progress_not_listed_under_unassigned(self):
        """Lines with no unassigned qty are not listed; totals count all assignments."""
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        item = IndustryOrderItem.objects.create(
            order=order,
            eve_type=self.eve_type,
            quantity=2,
            target_unit_price=Decimal("1000000000"),
            target_estimated_margin=Decimal("100000000"),
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item,
            character=self.builder2,
            quantity=2,
        )
        text = build_industry_daily_summary_message()
        self.assertIn(f"`{order.public_short_code}` [TST] Test Groups", text)
        self.assertNotIn(
            f"- `{order.public_short_code}` [TST] {self.eve_type.name}",
            text,
        )
        self.assertIn("**Total order amount:** 2B", text)

    def test_delivered_assignments_counted_in_totals(self):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        item = IndustryOrderItem.objects.create(
            order=order,
            eve_type=self.eve_type,
            quantity=2,
            target_unit_price=Decimal("1000000000"),
            target_estimated_margin=Decimal("100000000"),
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=item,
            character=self.builder2,
            quantity=2,
            delivered_at=timezone.now(),
        )
        text = build_industry_daily_summary_message()
        self.assertIn("**Total order amount:** 2B", text)
        self.assertIn("**Total available margin:** 0.2B", text)
