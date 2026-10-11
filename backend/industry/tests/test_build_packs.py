"""Tests for BUILD alliance pack matching and the claim-dialog endpoint."""

from datetime import timedelta
from decimal import Decimal

from django.test import Client
from django.utils import timezone
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveCorporationContract,
    EveLocation,
)
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase as AppTestCase
from industry.helpers.build_packs import (
    BUILD_ALLIANCE_ID,
    match_build_packs_for_item,
)
from industry.models import IndustryOrderItem
from industry.test_utils import create_industry_order


class BuildPackFixtureMixin:
    """Hulls, groups, a BUILD-assigned corp contract factory and an order line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eve_category, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        cls.cruiser_group, _ = EveGroup.objects.get_or_create(
            id=26,
            defaults={
                "name": "Cruiser",
                "published": True,
                "eve_category": cls.eve_category,
            },
        )
        cls.battlecruiser_group, _ = EveGroup.objects.get_or_create(
            id=419,
            defaults={
                "name": "Combat Battlecruiser",
                "published": True,
                "eve_category": cls.eve_category,
            },
        )

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.character = EveCharacter.objects.create(
            character_id=998001,
            character_name="Pack Tester",
            user=self.user,
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001, name="Test Builders"
        )
        self.location = EveLocation.objects.create(
            location_id=1998001,
            location_name="Amamake - Pack Depot",
            solar_system_id=300002,
            solar_system_name="Amamake",
            short_name="AMA",
        )
        self.vexor = EveType.objects.create(
            id=998101,
            name="Vexor",
            published=True,
            eve_group=self.cruiser_group,
        )
        self.cyclone_fleet_issue = EveType.objects.create(
            id=998102,
            name="Cyclone Fleet Issue",
            published=True,
            eve_group=self.battlecruiser_group,
        )
        self.order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        self.vexor_item = IndustryOrderItem.objects.create(
            order=self.order, eve_type=self.vexor, quantity=10
        )

    def make_contract(
        self,
        contract_id,
        title,
        *,
        status="outstanding",
        assignee_id=BUILD_ALLIANCE_ID,
        price=Decimal("21500000.00"),
        start_location_id=1998001,
        contract_type="item_exchange",
    ):
        return EveCorporationContract.objects.create(
            contract_id=contract_id,
            corporation=self.corporation,
            type=contract_type,
            status=status,
            availability="personal",
            issuer_id=998001,
            assignee_id=assignee_id,
            price=price,
            start_location_id=start_location_id,
            title=title,
        )


class BuildPackMatchingTestCase(BuildPackFixtureMixin, AppTestCase):
    """Title heuristics: hull BPC packs, group material packs, collapsing."""

    def test_matches_hull_bpc_pack(self):
        self.make_contract(1, "Vexor BPCs 10 runs each")
        packs = match_build_packs_for_item(self.vexor_item)
        self.assertEqual(len(packs), 1)
        self.assertEqual(packs[0].title, "Vexor BPCs 10 runs each")
        self.assertEqual(packs[0].count, 1)
        self.assertEqual(packs[0].price, Decimal("21500000.00"))
        self.assertEqual(packs[0].location_name, "Amamake - Pack Depot")

    def test_matches_material_pack_by_group_name(self):
        self.make_contract(2, "Navy Cruiser material pack")
        packs = match_build_packs_for_item(self.vexor_item)
        self.assertEqual(
            [pack.title for pack in packs], ["Navy Cruiser material pack"]
        )

    def test_matches_material_pack_by_last_word_of_group(self):
        """Group is "Combat Battlecruiser"; titles say just "Battlecruiser"."""
        item = IndustryOrderItem.objects.create(
            order=self.order, eve_type=self.cyclone_fleet_issue, quantity=4
        )
        self.make_contract(3, "Battlecruiser Mineral Pack")
        packs = match_build_packs_for_item(item)
        self.assertEqual(
            [pack.title for pack in packs], ["Battlecruiser Mineral Pack"]
        )

    def test_ignores_other_hull_bpc_pack(self):
        self.make_contract(4, "Algos BPC pack")
        self.assertEqual(match_build_packs_for_item(self.vexor_item), [])

    def test_ignores_hull_name_without_bpc_marker(self):
        self.make_contract(5, "Vexor hull, fitted")
        self.assertEqual(match_build_packs_for_item(self.vexor_item), [])

    def test_ignores_material_pack_for_another_group(self):
        self.make_contract(6, "Battleship material pack")
        self.assertEqual(match_build_packs_for_item(self.vexor_item), [])

    def test_ignores_finished_and_expired_contracts(self):
        self.make_contract(7, "Vexor BPCs 10 runs each", status="finished")
        self.make_contract(8, "Vexor BPCs 10 runs each", status="expired")
        self.assertEqual(match_build_packs_for_item(self.vexor_item), [])

    def test_ignores_contracts_assigned_elsewhere(self):
        self.make_contract(9, "Vexor BPCs 10 runs each", assignee_id=99011978)
        self.assertEqual(match_build_packs_for_item(self.vexor_item), [])

    def test_ignores_non_item_exchange_contracts(self):
        self.make_contract(
            10, "Vexor BPCs 10 runs each", contract_type="courier"
        )
        self.assertEqual(match_build_packs_for_item(self.vexor_item), [])

    def test_ignores_empty_titles(self):
        self.make_contract(11, "")
        self.assertEqual(match_build_packs_for_item(self.vexor_item), [])

    def test_collapses_identical_titles_at_same_price(self):
        for contract_id in (12, 13, 14, 15, 16):
            self.make_contract(contract_id, "Vexor BPC pack")
        packs = match_build_packs_for_item(self.vexor_item)
        self.assertEqual(len(packs), 1)
        self.assertEqual(packs[0].count, 5)

    def test_keeps_same_title_at_different_prices_apart(self):
        self.make_contract(17, "Vexor BPC pack", price=Decimal("1000000.00"))
        self.make_contract(18, "Vexor BPC pack", price=Decimal("2000000.00"))
        packs = match_build_packs_for_item(self.vexor_item)
        self.assertEqual(len(packs), 2)
        self.assertEqual(
            [pack.price for pack in packs],
            [Decimal("1000000.00"), Decimal("2000000.00")],
        )

    def test_omits_location_when_structure_untracked(self):
        self.make_contract(
            19, "Vexor BPC pack", start_location_id=1037716177931
        )
        packs = match_build_packs_for_item(self.vexor_item)
        self.assertEqual(len(packs), 1)
        self.assertIsNone(packs[0].location_name)

    def test_hull_match_is_one_directional(self):
        """A Vexor line matches a Navy Issue pack; the reverse does not."""
        navy_group_item = IndustryOrderItem.objects.create(
            order=self.order,
            eve_type=EveType.objects.create(
                id=998103,
                name="Vexor Navy Issue",
                published=True,
                eve_group=self.cruiser_group,
            ),
            quantity=3,
        )
        self.make_contract(20, "Vexor BPCs 10 runs each")
        self.assertEqual(len(match_build_packs_for_item(self.vexor_item)), 1)
        self.assertEqual(match_build_packs_for_item(navy_group_item), [])


class BuildPackEndpointTestCase(BuildPackFixtureMixin, AppTestCase):
    """GET /api/industry/orders/{id}/orderitems/{item_id}/build-packs (public)."""

    def endpoint(self, order_id, item_id):
        return (
            f"/api/industry/orders/{order_id}"
            f"/orderitems/{item_id}/build-packs"
        )

    def test_returns_matching_packs_without_auth(self):
        self.make_contract(30, "Vexor BPCs 10 runs each")
        self.make_contract(31, "Vexor BPCs 10 runs each")
        response = self.client.get(
            self.endpoint(self.order.pk, self.vexor_item.pk)
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Vexor BPCs 10 runs each")
        self.assertEqual(data[0]["count"], 2)
        self.assertEqual(data[0]["location_name"], "Amamake - Pack Depot")

    def test_returns_empty_list_when_no_packs(self):
        response = self.client.get(
            self.endpoint(self.order.pk, self.vexor_item.pk)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_404_for_unknown_order(self):
        response = self.client.get(self.endpoint(999999, self.vexor_item.pk))
        self.assertEqual(response.status_code, 404)

    def test_404_when_item_belongs_to_another_order(self):
        other_order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
            location=self.location,
        )
        response = self.client.get(
            self.endpoint(other_order.pk, self.vexor_item.pk)
        )
        self.assertEqual(response.status_code, 404)
