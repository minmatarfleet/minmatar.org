"""Tests for industry.helpers.type_breakdown."""

from django.test import TestCase

from eveuniverse.models import EveCategory, EveGroup, EveType

from industry.helpers.type_breakdown import (
    ACTIVITY_MANUFACTURING,
    ACTIVITY_REACTION,
    ComponentNode,
    break_down_type,
    flatten_components,
    get_flat_breakdown,
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

    def test_flatten_components_on_leaf_tree_returns_single_type(self):
        """Flattening a tree with no children returns the root type with its quantity."""
        eve_type = EveType.objects.create(
            id=999003,
            name="Leaf Type",
            published=True,
            eve_group=self.eve_group,
        )
        node = break_down_type(eve_type, quantity=2)
        flat = flatten_components(node)
        self.assertEqual(flat, {999003: 2})

    def test_flatten_components_aggregates_quantities(self):
        """Flatten aggregates same type from multiple branches (structure only)."""
        eve_type = EveType.objects.create(
            id=999004,
            name="Root",
            published=True,
            eve_group=self.eve_group,
        )
        child_type = EveType.objects.create(
            id=999005,
            name="Child",
            published=True,
            eve_group=self.eve_group,
        )
        node = ComponentNode(
            eve_type=eve_type,
            quantity=1,
            source="raw",
            depth=0,
            children=[
                ComponentNode(child_type, 3, "blueprint", 1, []),
                ComponentNode(child_type, 5, "blueprint", 1, []),
            ],
        )
        flat = flatten_components(node)
        self.assertEqual(flat[999005], 8)

    def test_get_flat_breakdown_returns_list_of_tuples(self):
        """get_flat_breakdown returns [(EveType, quantity), ...] for a type with no breakdown."""
        eve_type = EveType.objects.create(
            id=999006,
            name="Simple Type",
            published=True,
            eve_group=self.eve_group,
        )
        result = get_flat_breakdown(eve_type, quantity=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0].id, 999006)
        self.assertEqual(result[0][1], 1)

    def test_activity_constants(self):
        """Industry activity IDs match Eve SDE."""
        self.assertEqual(ACTIVITY_MANUFACTURING, 1)
        self.assertEqual(ACTIVITY_REACTION, 11)
