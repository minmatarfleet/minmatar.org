"""Tests for GET /api/industry/orders/character-statistics."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.test import TestCase as AppTestCase
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType
from industry.models import IndustryOrderItem, IndustryOrderItemAssignment
from industry.test_utils import create_industry_order
from tribes.models import Tribe, TribeGroup, TribeGroupMembership


class OrdersCharacterStatisticsTestCase(AppTestCase):
    """Delivered ISK estimate ranking for manufacturing production members."""

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
        self.eve_type = EveType.objects.create(
            id=999301,
            name="Test Hull",
            published=True,
            eve_group=self.eve_group,
        )
        self.location = EveLocation.objects.create(
            location_id=1999301,
            location_name="Stats Station",
            solar_system_id=300001,
            solar_system_name="Test System",
            short_name="SST",
        )

        self.supply = Tribe.objects.create(name="Supply", slug="supply")
        self.subcap = TribeGroup.objects.create(
            tribe=self.supply,
            name="Subcapital Production",
            code="supply.subcapital-production",
        )
        self.capital_prod = TribeGroup.objects.create(
            tribe=self.supply,
            name="Capital Production",
            code="supply.capital-production",
        )
        self.mining = TribeGroup.objects.create(
            tribe=self.supply,
            name="Mining",
            code="supply.mining",
        )

        self.member_user = User.objects.create_user(username="manufacturer")
        self.member_char = EveCharacter.objects.create(
            character_id=999311,
            character_name="Manufacturer Prim",
            user=self.member_user,
        )
        set_primary_character(self.member_user, self.member_char)
        TribeGroupMembership.objects.create(
            user=self.member_user,
            tribe_group=self.subcap,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

        self.capital_user = User.objects.create_user(username="capital_mfg")
        self.capital_char = EveCharacter.objects.create(
            character_id=999312,
            character_name="Capital Prim",
            user=self.capital_user,
        )
        set_primary_character(self.capital_user, self.capital_char)
        TribeGroupMembership.objects.create(
            user=self.capital_user,
            tribe_group=self.capital_prod,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

        self.miner_user = User.objects.create_user(username="miner_only")
        self.miner_char = EveCharacter.objects.create(
            character_id=999313,
            character_name="Miner Prim",
            user=self.miner_user,
        )
        set_primary_character(self.miner_user, self.miner_char)
        TribeGroupMembership.objects.create(
            user=self.miner_user,
            tribe_group=self.mining,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

        self.outsider_user = User.objects.create_user(username="outsider")
        self.outsider_char = EveCharacter.objects.create(
            character_id=999314,
            character_name="Outsider Prim",
            user=self.outsider_user,
        )
        set_primary_character(self.outsider_user, self.outsider_char)

        self.owner = EveCharacter.objects.create(
            character_id=999310,
            character_name="Order Owner",
            user=self.user,
        )

    def _make_delivered_assignment(
        self,
        *,
        character,
        quantity,
        unit_price,
        delivered_at=None,
        fulfilled_at=None,
        assignment_unit_price=None,
    ):
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.owner,
            location=self.location,
            fulfilled_at=fulfilled_at,
        )
        item = IndustryOrderItem.objects.create(
            order=order,
            eve_type=self.eve_type,
            quantity=quantity,
            target_unit_price=unit_price,
        )
        return IndustryOrderItemAssignment.objects.create(
            order_item=item,
            character=character,
            quantity=quantity,
            target_unit_price=assignment_unit_price,
            delivered_at=delivered_at,
        )

    def test_ranks_by_delivered_isk_estimate(self):
        now = timezone.now()
        self._make_delivered_assignment(
            character=self.member_char,
            quantity=10,
            unit_price=Decimal("1000000"),
            delivered_at=now - timedelta(days=1),
        )
        self._make_delivered_assignment(
            character=self.capital_char,
            quantity=5,
            unit_price=Decimal("1000000"),
            delivered_at=now - timedelta(days=2),
        )

        response = self.client.get("/api/industry/orders/character-statistics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["primary_character_id"], 999311)
        self.assertEqual(
            Decimal(data[0]["delivered_isk_estimate"]), Decimal("10000000")
        )
        self.assertEqual(data[1]["primary_character_id"], 999312)
        self.assertEqual(
            Decimal(data[1]["delivered_isk_estimate"]), Decimal("5000000")
        )

    def test_excludes_non_manufacturing_group_members(self):
        now = timezone.now()
        self._make_delivered_assignment(
            character=self.member_char,
            quantity=1,
            unit_price=Decimal("1000"),
            delivered_at=now - timedelta(days=1),
        )
        self._make_delivered_assignment(
            character=self.miner_char,
            quantity=100,
            unit_price=Decimal("1000"),
            delivered_at=now - timedelta(days=1),
        )
        self._make_delivered_assignment(
            character=self.outsider_char,
            quantity=1000,
            unit_price=Decimal("1000"),
            delivered_at=now - timedelta(days=1),
        )

        response = self.client.get("/api/industry/orders/character-statistics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["primary_character_id"], 999311)

    def test_excludes_deliveries_older_than_30_days(self):
        now = timezone.now()
        self._make_delivered_assignment(
            character=self.member_char,
            quantity=1,
            unit_price=Decimal("1000"),
            delivered_at=now - timedelta(days=31),
        )
        self._make_delivered_assignment(
            character=self.capital_char,
            quantity=2,
            unit_price=Decimal("1000"),
            delivered_at=now - timedelta(days=5),
        )

        response = self.client.get("/api/industry/orders/character-statistics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["primary_character_id"], 999312)

    def test_uses_order_fulfilled_at_when_assignment_not_marked(self):
        now = timezone.now()
        self._make_delivered_assignment(
            character=self.member_char,
            quantity=3,
            unit_price=Decimal("2000"),
            delivered_at=None,
            fulfilled_at=now - timedelta(days=3),
        )

        response = self.client.get("/api/industry/orders/character-statistics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(
            Decimal(data[0]["delivered_isk_estimate"]), Decimal("6000")
        )

    def test_assignment_unit_price_overrides_item(self):
        now = timezone.now()
        self._make_delivered_assignment(
            character=self.member_char,
            quantity=2,
            unit_price=Decimal("100"),
            assignment_unit_price=Decimal("500"),
            delivered_at=now - timedelta(days=1),
        )

        response = self.client.get("/api/industry/orders/character-statistics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(
            Decimal(data[0]["delivered_isk_estimate"]), Decimal("1000")
        )

    def test_inactive_membership_excluded(self):
        now = timezone.now()
        membership = TribeGroupMembership.objects.get(user=self.member_user)
        membership.status = TribeGroupMembership.STATUS_INACTIVE
        membership.save()

        self._make_delivered_assignment(
            character=self.member_char,
            quantity=10,
            unit_price=Decimal("1000"),
            delivered_at=now - timedelta(days=1),
        )

        response = self.client.get("/api/industry/orders/character-statistics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
