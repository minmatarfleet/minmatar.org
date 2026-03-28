"""Tests for 3-character public short codes."""

from datetime import timedelta

from django.utils import timezone

from app.test import TestCase as AppTestCase
from eveonline.models import EveCharacter

from industry.helpers.public_short_code import (
    generate_random_public_short_code,
    is_valid_public_short_code,
    pick_unique_public_short_code_among_actives,
    public_short_code_taken_by_active,
)
from industry.models import IndustryOrder
from industry.test_utils import create_industry_order


class PublicShortCodeTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.character = EveCharacter.objects.get_or_create(
            character_id=881001,
            defaults={"character_name": "C", "user": self.user},
        )[0]

    def test_generate_length_and_alphabet(self):
        c = generate_random_public_short_code()
        self.assertEqual(len(c), 3)
        self.assertTrue(is_valid_public_short_code(c))

    def test_pick_unique_avoids_active_collision(self):
        a = pick_unique_public_short_code_among_actives()
        create_industry_order(
            needed_by=(timezone.now() + timedelta(days=1)).date(),
            character=self.character,
            public_short_code=a,
        )
        b = pick_unique_public_short_code_among_actives()
        self.assertNotEqual(a, b)

    def test_fulfilled_same_code_allowed_for_second_order(self):
        code = "z9Z"
        create_industry_order(
            needed_by=(timezone.now() + timedelta(days=1)).date(),
            character=self.character,
            fulfilled_at=timezone.now(),
            public_short_code=code,
        )
        create_industry_order(
            needed_by=(timezone.now() + timedelta(days=2)).date(),
            character=self.character,
            fulfilled_at=timezone.now(),
            public_short_code=code,
        )
        self.assertEqual(
            IndustryOrder.objects.filter(public_short_code=code).count(), 2
        )

    def test_public_short_code_taken_by_active(self):
        code = pick_unique_public_short_code_among_actives()
        self.assertFalse(public_short_code_taken_by_active(code))
        o = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=1)).date(),
            character=self.character,
            public_short_code=code,
        )
        self.assertTrue(public_short_code_taken_by_active(code))
        self.assertFalse(
            public_short_code_taken_by_active(code, exclude_order_pk=o.pk)
        )
