"""Tests for Market Ops character statistics leaderboard."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db.models import signals as django_signals
from django.test import Client

from app.test import TestCase
from eveonline.helpers.characters import set_primary_character
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EveLocation,
)
from market.helpers.attributed_orders import (
    OrderSyncStatus,
    sync_character_orders,
    sync_corporation_orders,
)
from market.helpers.character_statistics import (
    build_market_character_statistics,
)
from market.helpers.market_operators import eligible_market_operator_user_ids
from market.models import EveMarketAttributedOrder, EveMarketContract
from tribes.models import Tribe, TribeGroup, TribeGroupMembership


def setUpModule():
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import user_group_changed

    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )


BASE_URL = "/api/market"


class MarketCharacterStatisticsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.location = EveLocation.objects.create(
            location_id=60003760,
            location_name="Staging Hub",
            solar_system_id=1,
            solar_system_name="Staging",
            market_active=True,
        )
        self.inactive_location = EveLocation.objects.create(
            location_id=60003761,
            location_name="Inactive Hub",
            solar_system_id=2,
            solar_system_name="Elsewhere",
            market_active=False,
        )
        self.tribe = Tribe.objects.create(name="Supply", slug="supply")
        self.market_group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Market",
            code="supply.market",
        )

        self.operator = User.objects.create_user(username="operator")
        self.operator_char = EveCharacter.objects.create(
            character_id=111001,
            character_name="Market Pilot",
            user=self.operator,
            esi_scope_groups=["Basic", "Market"],
        )
        set_primary_character(self.operator, self.operator_char)
        TribeGroupMembership.objects.create(
            tribe_group=self.market_group,
            user=self.operator,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

        self.other = User.objects.create_user(username="other")
        self.other_char = EveCharacter.objects.create(
            character_id=222002,
            character_name="Other Pilot",
            user=self.other,
            esi_scope_groups=["Basic", "Market"],
        )
        set_primary_character(self.other, self.other_char)
        TribeGroupMembership.objects.create(
            tribe_group=self.market_group,
            user=self.other,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

    def test_eligibility_requires_tribe_and_market_token(self):
        no_token = User.objects.create_user(username="no_token")
        EveCharacter.objects.create(
            character_id=333003,
            character_name="No Token",
            user=no_token,
            esi_scope_groups=["Basic"],
        )
        TribeGroupMembership.objects.create(
            tribe_group=self.market_group,
            user=no_token,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

        token_only = User.objects.create_user(username="token_only")
        EveCharacter.objects.create(
            character_id=444004,
            character_name="Token Only",
            user=token_only,
            esi_scope_groups=["Market"],
        )

        eligible = eligible_market_operator_user_ids()
        self.assertIn(self.operator.id, eligible)
        self.assertIn(self.other.id, eligible)
        self.assertNotIn(no_token.id, eligible)
        self.assertNotIn(token_only.id, eligible)

    def test_ranks_by_sell_orders_and_contracts(self):
        EveMarketAttributedOrder.objects.create(
            order_id=1,
            type_id=34,
            location_esi_id=self.location.location_id,
            price=Decimal("1000000"),
            volume_remain=10,
            is_buy_order=False,
            owner_character_id=self.operator_char.character_id,
        )
        EveMarketContract.objects.create(
            id=9001,
            status="outstanding",
            title="Fit A",
            price=Decimal("5000000"),
            issuer_external_id=self.operator_char.character_id,
            location=self.location,
        )
        EveMarketAttributedOrder.objects.create(
            order_id=2,
            type_id=35,
            location_esi_id=self.location.location_id,
            price=Decimal("2000000"),
            volume_remain=5,
            is_buy_order=False,
            owner_character_id=self.other_char.character_id,
        )

        rows = build_market_character_statistics()
        self.assertEqual(2, len(rows))
        self.assertEqual("Market Pilot", rows[0].primary_character_name)
        self.assertEqual(15_000_000.0, rows[0].total_isk_on_market)
        self.assertEqual("Other Pilot", rows[1].primary_character_name)
        self.assertEqual(10_000_000.0, rows[1].total_isk_on_market)

    def test_excludes_buy_orders_inactive_locations_and_corp_id_contracts(
        self,
    ):
        EveMarketAttributedOrder.objects.create(
            order_id=3,
            type_id=34,
            location_esi_id=self.location.location_id,
            price=Decimal("100"),
            volume_remain=1,
            is_buy_order=True,
            owner_character_id=self.operator_char.character_id,
        )
        EveMarketAttributedOrder.objects.create(
            order_id=4,
            type_id=34,
            location_esi_id=self.inactive_location.location_id,
            price=Decimal("999999"),
            volume_remain=10,
            is_buy_order=False,
            owner_character_id=self.operator_char.character_id,
        )
        EveMarketContract.objects.create(
            id=9002,
            status="outstanding",
            title="Corp issued",
            price=Decimal("8000000"),
            issuer_external_id=98765432,  # corp id, not character
            location=self.location,
        )

        self.assertEqual([], build_market_character_statistics())

    def test_corp_issued_by_attribution_counts_for_issuer(self):
        EveMarketAttributedOrder.objects.create(
            order_id=5,
            type_id=34,
            location_esi_id=self.location.location_id,
            price=Decimal("250000"),
            volume_remain=4,
            is_buy_order=False,
            owner_character_id=self.operator_char.character_id,
            corporation_id=98000001,
        )

        rows = build_market_character_statistics()
        self.assertEqual(1, len(rows))
        self.assertEqual(1_000_000.0, rows[0].total_isk_on_market)
        self.assertEqual(111001, rows[0].primary_character_id)

    def test_endpoint_returns_sorted_payload(self):
        EveMarketAttributedOrder.objects.create(
            order_id=6,
            type_id=34,
            location_esi_id=self.location.location_id,
            price=Decimal("3000000"),
            volume_remain=1,
            is_buy_order=False,
            owner_character_id=self.other_char.character_id,
        )
        EveMarketAttributedOrder.objects.create(
            order_id=7,
            type_id=34,
            location_esi_id=self.location.location_id,
            price=Decimal("1000000"),
            volume_remain=1,
            is_buy_order=False,
            owner_character_id=self.operator_char.character_id,
        )

        response = self.client.get(f"{BASE_URL}/character-statistics")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(2, len(data))
        self.assertEqual("Other Pilot", data[0]["primary_character_name"])
        self.assertEqual(3_000_000.0, data[0]["total_isk_on_market"])
        self.assertEqual("Market Pilot", data[1]["primary_character_name"])


class AttributedOrderSyncTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.character = EveCharacter.objects.create(
            character_id=555005,
            character_name="Sync Pilot",
            user=self.user,
            esi_scope_groups=["Market"],
        )

    @patch("market.helpers.attributed_orders.EsiClient")
    def test_sync_character_orders_replaces_personal(self, esi_cls):
        EveMarketAttributedOrder.objects.create(
            order_id=100,
            type_id=34,
            location_esi_id=1,
            price=Decimal("1"),
            volume_remain=1,
            is_buy_order=False,
            owner_character_id=self.character.character_id,
        )
        client = MagicMock()
        esi_cls.return_value = client
        response = MagicMock()
        response.success.return_value = True
        response.results.return_value = [
            {
                "order_id": 200,
                "type_id": 35,
                "location_id": 60003760,
                "price": 12.5,
                "volume_remain": 3,
                "is_buy_order": False,
                "issued": "2026-01-01T00:00:00Z",
                "duration": 90,
            }
        ]
        client.get_character_orders.return_value = response

        result = sync_character_orders(self.character.character_id)
        self.assertEqual(OrderSyncStatus.OK, result.status)
        self.assertEqual(1, result.rows)
        self.assertFalse(
            EveMarketAttributedOrder.objects.filter(order_id=100).exists()
        )
        order = EveMarketAttributedOrder.objects.get(order_id=200)
        self.assertEqual(self.character.character_id, order.owner_character_id)
        self.assertIsNone(order.corporation_id)
        self.assertEqual(Decimal("12.50"), order.price)

    @patch("market.helpers.attributed_orders.get_director_with_scope")
    @patch("market.helpers.attributed_orders.EsiClient")
    def test_sync_corporation_orders_uses_issued_by(
        self, esi_cls, get_director
    ):
        alliance = EveAlliance.objects.create(
            alliance_id=99000001, name="Minmatar Fleet Alliance"
        )
        corp = EveCorporation.objects.create(
            corporation_id=98000099,
            name="Market Corp",
            alliance=alliance,
        )
        get_director.return_value = self.character
        client = MagicMock()
        esi_cls.return_value = client
        response = MagicMock()
        response.success.return_value = True
        response.results.return_value = [
            {
                "order_id": 300,
                "type_id": 36,
                "location_id": 60003760,
                "price": 50,
                "volume_remain": 2,
                "is_buy_order": False,
                "issued_by": 777007,
                "issued": "2026-01-02T00:00:00Z",
                "duration": 30,
            },
            {
                "order_id": 301,
                "type_id": 36,
                "location_id": 60003760,
                "price": 10,
                "volume_remain": 1,
                "is_buy_order": False,
                # missing issued_by -> skipped
            },
        ]
        client.get_corporation_orders.return_value = response

        result = sync_corporation_orders(corp.corporation_id)
        self.assertEqual(OrderSyncStatus.OK, result.status)
        self.assertEqual(1, result.rows)
        order = EveMarketAttributedOrder.objects.get(order_id=300)
        self.assertEqual(777007, order.owner_character_id)
        self.assertEqual(98000099, order.corporation_id)

    @patch("market.helpers.attributed_orders.get_director_with_scope")
    @patch("market.helpers.attributed_orders.EsiClient")
    def test_sync_corporation_orders_replaces_personal_same_order_id(
        self, esi_cls, get_director
    ):
        """Personal↔corp ownership of the same ESI order_id must not IntegrityError."""
        EveMarketAttributedOrder.objects.create(
            order_id=400,
            type_id=34,
            location_esi_id=1,
            price=Decimal("1"),
            volume_remain=1,
            is_buy_order=False,
            owner_character_id=self.character.character_id,
            corporation_id=None,
        )
        alliance = EveAlliance.objects.create(
            alliance_id=99000002, name="Minmatar Fleet Alliance"
        )
        corp = EveCorporation.objects.create(
            corporation_id=98000100,
            name="Market Corp 2",
            alliance=alliance,
        )
        get_director.return_value = self.character
        client = MagicMock()
        esi_cls.return_value = client
        response = MagicMock()
        response.success.return_value = True
        response.results.return_value = [
            {
                "order_id": 400,
                "type_id": 34,
                "location_id": 60003760,
                "price": 99.5,
                "volume_remain": 5,
                "is_buy_order": False,
                "issued_by": self.character.character_id,
                "issued": "2026-01-03T00:00:00Z",
                "duration": 30,
            }
        ]
        client.get_corporation_orders.return_value = response

        result = sync_corporation_orders(corp.corporation_id)
        self.assertEqual(OrderSyncStatus.OK, result.status)
        self.assertEqual(1, result.rows)
        order = EveMarketAttributedOrder.objects.get(order_id=400)
        self.assertEqual(self.character.character_id, order.owner_character_id)
        self.assertEqual(98000100, order.corporation_id)
        self.assertEqual(Decimal("99.50"), order.price)
        self.assertEqual(
            1, EveMarketAttributedOrder.objects.filter(order_id=400).count()
        )
