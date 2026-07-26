"""Tests for loose industry order ↔ ESI contract associations."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone

from app.test import TestCase
from eveonline.models import EveCharacter, EveCharacterContract, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType

from industry.helpers.contract_associations import (
    MATCH_THRESHOLD,
    match_order_contracts,
    reconcile_order_contract_associations,
)
from industry.models import (
    IndustryContractAssociation,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)
from industry.tasks import (
    reconcile_industry_contract_associations_for_character_task,
    reconcile_industry_contract_associations_task,
)
from industry.test_utils import create_industry_order


class ContractAssociationTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category, _ = EveCategory.objects.get_or_create(
            id=9201,
            defaults={"name": "Assoc Category", "published": True},
        )
        cls.group, _ = EveGroup.objects.get_or_create(
            id=9201,
            defaults={
                "name": "Assoc Group",
                "published": True,
                "eve_category": cls.category,
            },
        )
        cls.eve_type, _ = EveType.objects.get_or_create(
            id=9201,
            defaults={
                "name": "Assoc Widget",
                "published": True,
                "eve_group": cls.group,
            },
        )
        cls.eve_type_b, _ = EveType.objects.get_or_create(
            id=9202,
            defaults={
                "name": "Assoc Widget B",
                "published": True,
                "eve_group": cls.group,
            },
        )

    def setUp(self):
        self.user = User.objects.create_user(username="assoc_owner")
        self.location = EveLocation.objects.create(
            location_id=92001,
            location_name="Assoc Hub",
            solar_system_id=1,
            solar_system_name="Test",
        )
        self.owner = EveCharacter.objects.create(
            character_id=92001,
            character_name="Order Owner",
            corporation_id=98000001,
            alliance_id=99000001,
            user=self.user,
        )
        self.builder = EveCharacter.objects.create(
            character_id=92002,
            character_name="Builder Pilot",
            user=self.user,
        )
        self.needed_by = (timezone.now() + timedelta(days=7)).date()
        self.order = create_industry_order(
            needed_by=self.needed_by,
            character=self.owner,
            location=self.location,
            public_short_code="aB3",
            contract_to="Order Owner",
        )
        self.order_item = IndustryOrderItem.objects.create(
            order=self.order,
            eve_type=self.eve_type,
            quantity=10,
        )
        self.assignment = IndustryOrderItemAssignment.objects.create(
            order_item=self.order_item,
            character=self.builder,
            quantity=5,
        )

    def _make_contract(self, **overrides):
        defaults = {
            "contract_id": 700001,
            "character": self.owner,
            "type": "item_exchange",
            "status": "outstanding",
            "issuer_id": self.builder.character_id,
            "assignee_id": self.owner.character_id,
            "date_issued": timezone.now(),
            "start_location_id": self.location.location_id,
            "end_location_id": self.location.location_id,
            "title": "Delivery aB3",
        }
        defaults.update(overrides)
        return EveCharacterContract.objects.create(**defaults)

    def test_no_association_when_assignee_does_not_match(self):
        self._make_contract(assignee_id=11111111, title="")
        candidates = match_order_contracts(
            self.order,
            fetch_items=False,
            item_quantities_by_contract={},
        )
        self.assertEqual(candidates, [])

    def test_assignee_and_issuer_and_type_score_assignment(self):
        contract = self._make_contract()
        candidates = match_order_contracts(
            self.order,
            fetch_items=False,
            item_quantities_by_contract={
                contract.contract_id: {self.eve_type.id: 5},
            },
        )
        self.assertEqual(len(candidates), 1)
        match = candidates[0]
        self.assertEqual(match.assignment.pk, self.assignment.pk)
        self.assertGreaterEqual(match.score, MATCH_THRESHOLD)
        self.assertTrue(match.signals.get("assignee_owner"))
        self.assertTrue(match.signals.get("issuer_assignee"))
        self.assertEqual(match.signals.get("type_qty"), 5)
        self.assertTrue(match.signals.get("location"))
        self.assertTrue(match.signals.get("short_code"))

    def test_order_level_when_no_assignment_pins(self):
        # Different issuer, no items → assignment score may still pass via
        # assignee+location+short_code+status; remove short code/location to
        # force order-level-only path without issuer/type.
        IndustryOrderItemAssignment.objects.all().delete()
        contract = self._make_contract(
            issuer_id=99999999,
            title="",
            start_location_id=None,
            end_location_id=None,
        )
        candidates = match_order_contracts(
            self.order,
            fetch_items=False,
            item_quantities_by_contract={contract.contract_id: {}},
        )
        self.assertEqual(len(candidates), 1)
        self.assertIsNone(candidates[0].assignment)
        self.assertTrue(candidates[0].signals.get("assignee_owner"))

    def test_multi_assignment_single_contract(self):
        item_b = IndustryOrderItem.objects.create(
            order=self.order,
            eve_type=self.eve_type_b,
            quantity=3,
        )
        assignment_b = IndustryOrderItemAssignment.objects.create(
            order_item=item_b,
            character=self.builder,
            quantity=3,
        )
        contract = self._make_contract()
        candidates = match_order_contracts(
            self.order,
            fetch_items=False,
            item_quantities_by_contract={
                contract.contract_id: {
                    self.eve_type.id: 5,
                    self.eve_type_b.id: 3,
                },
            },
        )
        assignment_ids = {c.assignment.pk for c in candidates}
        self.assertEqual(assignment_ids, {self.assignment.pk, assignment_b.pk})

    def test_reconcile_idempotent_upsert_and_prune(self):
        contract = self._make_contract()
        items = {contract.contract_id: {self.eve_type.id: 5}}
        written = reconcile_order_contract_associations(
            self.order,
            fetch_items=False,
            item_quantities_by_contract=items,
        )
        self.assertEqual(written, 1)
        self.assertEqual(IndustryContractAssociation.objects.count(), 1)

        written_again = reconcile_order_contract_associations(
            self.order,
            fetch_items=False,
            item_quantities_by_contract=items,
        )
        self.assertEqual(written_again, 1)
        self.assertEqual(IndustryContractAssociation.objects.count(), 1)

        # Change assignee so match disappears → prune
        contract.assignee_id = 11111111
        contract.save(update_fields=["assignee_id"])
        reconcile_order_contract_associations(
            self.order,
            fetch_items=False,
            item_quantities_by_contract=items,
        )
        self.assertEqual(IndustryContractAssociation.objects.count(), 0)

    def test_corp_assignee_matches_owner_corporation(self):
        contract = self._make_contract(
            assignee_id=self.owner.corporation_id,
            title="",
        )
        candidates = match_order_contracts(
            self.order,
            fetch_items=False,
            item_quantities_by_contract={
                contract.contract_id: {self.eve_type.id: 2},
            },
        )
        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0].signals.get("assignee_owner"))

    @patch("industry.tasks.reconcile_open_order_contract_associations")
    def test_reconcile_task_delegates(self, reconcile_mock):
        reconcile_mock.return_value = 3
        self.assertEqual(reconcile_industry_contract_associations_task(), 3)
        reconcile_mock.assert_called_once_with(fetch_items=True)

    @patch("industry.tasks.reconcile_associations_for_character")
    def test_reconcile_for_character_task(self, reconcile_mock):
        reconcile_mock.return_value = 1
        self.assertEqual(
            reconcile_industry_contract_associations_for_character_task(92001),
            1,
        )
        reconcile_mock.assert_called_once_with(92001, fetch_items=True)
