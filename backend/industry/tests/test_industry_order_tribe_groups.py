"""IndustryOrder.tribe_groups M2M to TribeGroup."""

from datetime import timedelta

from django.utils import timezone

from app.test import TestCase as AppTestCase
from eveonline.models import EveCharacter
from industry.test_utils import create_industry_order
from tribes.models import Tribe, TribeGroup


class IndustryOrderTribeGroupsTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.char = EveCharacter.objects.create(
            character_id=888001,
            character_name="Industry Char",
            user=self.user,
        )

    def test_tribe_groups_m2m(self):
        tribe = Tribe.objects.create(
            name="Industry Test", slug="industry-test"
        )
        tg = TribeGroup.objects.create(tribe=tribe, name="Subcapital")
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.char,
        )
        order.tribe_groups.add(tg)
        order.refresh_from_db()
        self.assertEqual(list(order.tribe_groups.all()), [tg])
        self.assertEqual(tg.industry_orders.count(), 1)
        self.assertEqual(tg.industry_orders.first().pk, order.pk)

    def test_tribe_groups_clear(self):
        tribe = Tribe.objects.create(name="T2", slug="t2")
        tg1 = TribeGroup.objects.create(tribe=tribe, name="A")
        tg2 = TribeGroup.objects.create(tribe=tribe, name="B")
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.char,
        )
        order.tribe_groups.set([tg1, tg2])
        self.assertEqual(order.tribe_groups.count(), 2)
        order.tribe_groups.clear()
        self.assertEqual(order.tribe_groups.count(), 0)
