"""Unit tests for assignment delivery quantity helpers."""

from django.test import SimpleTestCase
from django.utils import timezone

from industry.helpers.order_assignments import apply_assignment_delivery


class _FakeAssignment:
    def __init__(
        self, quantity: int, delivered_quantity: int = 0, delivered_at=None
    ):
        self.quantity = quantity
        self.delivered_quantity = delivered_quantity
        self.delivered_at = delivered_at


class ApplyAssignmentDeliveryTests(SimpleTestCase):
    def test_full_delivery_without_quantity(self):
        a = _FakeAssignment(quantity=50)
        err = apply_assignment_delivery(a, delivered=True)
        self.assertIsNone(err)
        self.assertEqual(a.delivered_quantity, 50)
        self.assertIsNotNone(a.delivered_at)

    def test_partial_then_complete(self):
        a = _FakeAssignment(quantity=50)
        err = apply_assignment_delivery(a, delivered=True, quantity=39)
        self.assertIsNone(err)
        self.assertEqual(a.delivered_quantity, 39)
        self.assertIsNone(a.delivered_at)

        err = apply_assignment_delivery(a, delivered=True, quantity=11)
        self.assertIsNone(err)
        self.assertEqual(a.delivered_quantity, 50)
        self.assertIsNotNone(a.delivered_at)

    def test_omit_quantity_completes_remaining(self):
        a = _FakeAssignment(quantity=50, delivered_quantity=39)
        err = apply_assignment_delivery(a, delivered=True)
        self.assertIsNone(err)
        self.assertEqual(a.delivered_quantity, 50)
        self.assertIsNotNone(a.delivered_at)

    def test_rejects_over_remaining(self):
        a = _FakeAssignment(quantity=50, delivered_quantity=39)
        err = apply_assignment_delivery(a, delivered=True, quantity=12)
        self.assertIn("Only 11", err or "")
        self.assertEqual(a.delivered_quantity, 39)

    def test_revert_clears_progress(self):
        a = _FakeAssignment(
            quantity=50,
            delivered_quantity=39,
            delivered_at=timezone.now(),
        )
        err = apply_assignment_delivery(a, delivered=False)
        self.assertIsNone(err)
        self.assertEqual(a.delivered_quantity, 0)
        self.assertIsNone(a.delivered_at)
