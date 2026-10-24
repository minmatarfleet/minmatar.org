"""Tests for industry.helpers.type_breakdown."""

from django.test import TestCase

from eveuniverse.models import EveCategory, EveGroup, EveType

from industry.helpers.type_breakdown import (
    ACTIVITY_MANUFACTURING,
    ACTIVITY_REACTION,
    ComponentNode,
    break_down_type,
)


class TypeBreakdownTestCase(TestCase):
    """Tests for type breakdown utility."""

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

    def test_break_down_type_with_no_components_returns_single_node(self):
        """A type with no materials and no blueprint/reaction returns one node, no children."""
        eve_type = EveType.objects.create(
            id=999001,
            name="Test Mineral",
            published=True,
            eve_group=self.eve_group,
        )
        node = break_down_type(eve_type, quantity=1)
        self.assertIsInstance(node, ComponentNode)
        self.assertEqual(node.eve_type.id, 999001)
        self.assertEqual(node.quantity, 1)
        self.assertEqual(node.depth, 0)
        self.assertEqual(len(node.children), 0)

    def test_break_down_type_with_quantity_multiplier(self):
        """Quantity is passed through to the root node."""
        eve_type = EveType.objects.create(
            id=999002,
            name="Test Item",
            published=True,
            eve_group=self.eve_group,
        )
        node = break_down_type(eve_type, quantity=10)
        self.assertEqual(node.quantity, 10)

    def test_activity_constants(self):
        """Industry activity IDs match Eve SDE."""
        self.assertEqual(ACTIVITY_MANUFACTURING, 1)
        self.assertEqual(ACTIVITY_REACTION, 11)
