"""Tests for Discord summary presentation helpers."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from app.test import TestCase as AppTestCase
from eveonline.models import EveCharacter, EveLocation

from industry.helpers.discord_summary_display import (
    format_isk_billions_trimmed,
    format_margin_profit_parenthetical,
    order_location_short_label,
    pluralize_eve_group_name,
)
from industry.test_utils import create_industry_order


class DiscordSummaryDisplayTests(AppTestCase):
    def test_pluralize_last_word(self):
        self.assertEqual(
            pluralize_eve_group_name("Energy Weapon"), "Energy Weapons"
        )
        self.assertEqual(pluralize_eve_group_name("Battleship"), "Battleships")

    def test_order_location_short_label(self):
        character = EveCharacter.objects.get_or_create(
            character_id=882001,
            defaults={"character_name": "C", "user": self.user},
        )[0]
        loc = EveLocation.objects.create(
            location_id=1882001,
            location_name="Long Name Here",
            solar_system_id=1,
            solar_system_name="S",
            short_name="  SN  ",
        )
        order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=character,
            location=loc,
        )
        self.assertEqual(order_location_short_label(order), "SN")

    def test_format_profit_parenthetical(self):
        self.assertEqual(
            format_margin_profit_parenthetical(Decimal("2000000000")),
            "(2B profit)",
        )
        self.assertEqual(
            format_margin_profit_parenthetical(Decimal("0")),
            "(0B profit)",
        )

    def test_format_isk_billions_trimmed(self):
        self.assertEqual(
            format_isk_billions_trimmed(Decimal("1500000000")), "1.5B"
        )
