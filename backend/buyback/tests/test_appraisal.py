"""Tests for buyback paste parse, classify, price, and appraise endpoint."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from buyback.helpers.accepted_items import (
    compressed_highsec_base,
    seed_accepted_items,
)
from buyback.helpers.classify import BuybackCategory, classify_eve_type
from buyback.helpers.paste import parse_eve_paste
from buyback.helpers.pricing import (
    get_baseline_buy_prices,
    get_baseline_buy_prices_by_name,
    merge_rate_rules,
    price_flat_line,
    price_ore_line,
)
from buyback.models import BuybackAcceptedItem, EveBuybackSettings
from eveonline.models import EveCharacter, EveLocation
from industry.models import IndustryOrder, IndustryOrderItem, IndustryProduct
from market.models import EveMarketItemHistory, EveMarketItemLocationPrice

BASE_URL = "/api/buyback"


def _ensure_type(
    *,
    type_id: int,
    name: str,
    group_id: int,
    group_name: str,
    category_id: int,
    category_name: str,
) -> EveType:
    category, _ = EveCategory.objects.get_or_create(
        id=category_id,
        defaults={"name": category_name, "published": True},
    )
    if category.name != category_name:
        category.name = category_name
        category.save(update_fields=["name"])
    group, _ = EveGroup.objects.get_or_create(
        id=group_id,
        defaults={
            "name": group_name,
            "eve_category": category,
            "published": True,
        },
    )
    if group.name != group_name or group.eve_category_id != category.id:
        group.name = group_name
        group.eve_category = category
        group.save()
    eve_type, _ = EveType.objects.get_or_create(
        id=type_id,
        defaults={
            "name": name,
            "eve_group": group,
            "published": True,
        },
    )
    if eve_type.name != name or eve_type.eve_group_id != group.id:
        eve_type.name = name
        eve_type.eve_group = group
        eve_type.save()
    return eve_type


class ParseEvePasteTestCase(TestCase):
    def test_tab_separated(self):
        lines = parse_eve_paste("Compressed Veldspar\t1000\nWater\t50")
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].name, "Compressed Veldspar")
        self.assertEqual(lines[0].quantity, 1000)
        self.assertEqual(lines[1].name, "Water")
        self.assertEqual(lines[1].quantity, 50)

    def test_aggregates_duplicates(self):
        lines = parse_eve_paste("Water\t10\nWater\t15")
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].quantity, 25)

    def test_comma_quantity_and_multibuy(self):
        lines = parse_eve_paste(
            "Compressed Veldspar 1,000\n100x Coolant\nScorched Telemetry Processor x2"
        )
        by_name = {line.name: line.quantity for line in lines}
        self.assertEqual(by_name["Compressed Veldspar"], 1000)
        self.assertEqual(by_name["Coolant"], 100)
        self.assertEqual(by_name["Scorched Telemetry Processor"], 2)

    def test_skips_header(self):
        paste = "Item\tQuantity\tVolume\nCompressed Veldspar\t100\t1.0"
        lines = parse_eve_paste(paste)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].name, "Compressed Veldspar")


class ClassifyBuybackTestCase(TestCase):
    def setUp(self):
        self.ore = _ensure_type(
            type_id=62516,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        self.ice = _ensure_type(
            type_id=28433,
            name="Compressed Blue Ice",
            group_id=465,
            group_name="Ice",
            category_id=25,
            category_name="Asteroid",
        )
        self.kangite = _ensure_type(
            type_id=92821,
            name="Compressed Kangite X-Grade",
            group_id=5086,
            group_name="Kangite",
            category_id=25,
            category_name="Asteroid",
        )
        self.p1 = _ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        self.p2 = _ensure_type(
            type_id=9832,
            name="Coolant",
            group_id=1034,
            group_name="Refined Commodities - Tier 2",
            category_id=43,
            category_name="Planetary Commodities",
        )
        self.salvage = _ensure_type(
            type_id=25588,
            name="Scorched Telemetry Processor",
            group_id=754,
            group_name="Salvaged Materials",
            category_id=4,
            category_name="Material",
        )
        self.mineral = _ensure_type(
            type_id=34,
            name="Tritanium",
            group_id=18,
            group_name="Mineral",
            category_id=4,
            category_name="Material",
        )

    def test_categories(self):
        self.assertEqual(
            classify_eve_type(self.ore).category, BuybackCategory.ORE
        )
        self.assertEqual(
            classify_eve_type(self.p1).category, BuybackCategory.P1
        )
        self.assertEqual(
            classify_eve_type(self.p2).category, BuybackCategory.PI_OTHER
        )
        self.assertEqual(
            classify_eve_type(self.salvage).category, BuybackCategory.SALVAGE
        )
        self.assertEqual(
            classify_eve_type(self.ice).category, BuybackCategory.EXCLUDED
        )
        self.assertEqual(
            classify_eve_type(self.kangite).category, BuybackCategory.EXCLUDED
        )
        self.assertEqual(
            classify_eve_type(self.mineral).category, BuybackCategory.UNKNOWN
        )


class PriceBuybackTestCase(TestCase):
    def test_merge_rate_rules_includes_other(self):
        rules = merge_rate_rules({})
        self.assertEqual(rules["other_jita_buy"], 1.0)
        rules = merge_rate_rules({"other_jita_buy": 0.95})
        self.assertEqual(rules["other_jita_buy"], 0.95)

    def test_price_flat_p1(self):
        line = price_flat_line(
            name="Water",
            quantity=100,
            type_id=3645,
            category=BuybackCategory.P1,
            rate=0.9,
            buy_price=Decimal("100"),
        )
        self.assertTrue(line.accepted)
        self.assertEqual(line.unit_price, 90.0)
        self.assertEqual(line.line_total, 9000.0)

    @patch("buyback.helpers.pricing.reprocess_output")
    def test_price_ore_uses_mineral_buys(self, mock_reprocess):
        mock_reprocess.return_value = {"Tritanium": 1000, "Pyerite": 100}
        line = price_ore_line(
            name="Compressed Veldspar",
            quantity=100,
            type_id=62516,
            refine_rate=0.85,
            ore_jita_buy=1.0,
            mineral_buy_by_name={
                "Tritanium": Decimal("4"),
                "Pyerite": Decimal("20"),
            },
        )
        self.assertTrue(line.accepted)
        # 1000*4 + 100*20 = 6000
        self.assertEqual(line.line_total, 6000.0)
        mock_reprocess.assert_called_once_with(
            "Compressed Veldspar", 100, refine_rate=0.85
        )


class BaselineBuyPriceFallbackTestCase(TestCase):
    def setUp(self):
        self.baseline = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=10000002,
            price_baseline=True,
            prices_active=True,
            market_active=False,
        )
        self.trit = _ensure_type(
            type_id=34,
            name="Tritanium",
            group_id=18,
            group_name="Mineral",
            category_id=4,
            category_name="Material",
        )
        self.water = _ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        EveMarketItemLocationPrice.objects.create(
            location=self.baseline,
            item=self.water,
            sell_price=Decimal("110"),
            buy_price=Decimal("100"),
            split_price=Decimal("105"),
        )
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.trit,
            date=date(2026, 7, 31),
            average=Decimal("3.93"),
            highest=Decimal("3.94"),
            lowest=Decimal("3.89"),
            volume=1_000_000,
        )

    def test_uses_location_buy_when_present(self):
        prices = get_baseline_buy_prices([self.water.id])
        self.assertEqual(prices[self.water.id], Decimal("100"))

    def test_falls_back_to_region_history_average(self):
        prices = get_baseline_buy_prices([self.trit.id])
        self.assertEqual(prices[self.trit.id], Decimal("3.93"))

        by_name = get_baseline_buy_prices_by_name(["Tritanium", "Water"])
        self.assertEqual(by_name["Tritanium"], Decimal("3.93"))
        self.assertEqual(by_name["Water"], Decimal("100"))


class AcceptedItemsSeedTestCase(TestCase):
    def test_compressed_highsec_base_matches_variants(self):
        self.assertEqual(
            compressed_highsec_base("Compressed Veldspar"), "Veldspar"
        )
        self.assertEqual(
            compressed_highsec_base("Compressed Veldspar II-Grade"),
            "Veldspar",
        )
        self.assertEqual(
            compressed_highsec_base("Compressed Brimful Zeolites"),
            "Zeolites",
        )
        self.assertIsNone(compressed_highsec_base("Veldspar"))
        self.assertIsNone(compressed_highsec_base("Compressed Blue Ice"))
        self.assertIsNone(compressed_highsec_base("Compressed Arkonor"))

    @patch("eveonline.signals.update_character_public_data")
    def test_seed_upserts_allowlist(self, unused_mock_public):
        ore = _ensure_type(
            type_id=62516,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        p1 = _ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        unused_p1 = _ensure_type(
            type_id=3683,
            name="Oxygen",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        product = _ensure_type(
            type_id=999001,
            name="Test Hull",
            group_id=25,
            group_name="Frigate",
            category_id=6,
            category_name="Ship",
        )
        _ensure_type(
            type_id=34,
            name="Tritanium",
            group_id=18,
            group_name="Mineral",
            category_id=4,
            category_name="Material",
        )
        IndustryProduct.objects.create(
            eve_type=product,
            strategy="imported",
            breakdown={
                "name": "Test Hull",
                "type_id": product.id,
                "quantity": 1,
                "children": [
                    {
                        "name": "Water",
                        "type_id": p1.id,
                        "quantity": 10,
                        "children": [],
                    }
                ],
            },
        )
        character = EveCharacter.objects.create(
            character_id=9001,
            character_name="Seed Tester",
        )
        order = IndustryOrder.objects.create(
            character=character,
            needed_by=timezone.now().date(),
            public_short_code="ABC",
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=product, quantity=1
        )
        BuybackAcceptedItem.objects.create(
            eve_type=unused_p1,
            category=BuybackAcceptedItem.Category.P1,
            active=True,
        )

        result = seed_accepted_items()
        self.assertGreaterEqual(result["seeded"], 2)
        self.assertEqual(result["pi_seeded"], 1)
        self.assertTrue(
            BuybackAcceptedItem.objects.filter(
                eve_type=ore, active=True, category="ore"
            ).exists()
        )
        self.assertTrue(
            BuybackAcceptedItem.objects.filter(
                eve_type=p1, active=True, category="p1"
            ).exists()
        )
        self.assertFalse(
            BuybackAcceptedItem.objects.filter(
                eve_type=unused_p1, active=True
            ).exists()
        )
        self.assertFalse(
            BuybackAcceptedItem.objects.filter(eve_type_id=34).exists()
        )


class AppraiseEndpointTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.baseline = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            price_baseline=True,
        )
        self.ore = _ensure_type(
            type_id=62516,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        self.uncompressed = _ensure_type(
            type_id=1230,
            name="Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        self.p1 = _ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        self.p2 = _ensure_type(
            type_id=9832,
            name="Coolant",
            group_id=1034,
            group_name="Refined Commodities - Tier 2",
            category_id=43,
            category_name="Planetary Commodities",
        )
        self.ice = _ensure_type(
            type_id=28433,
            name="Compressed Blue Ice",
            group_id=465,
            group_name="Ice",
            category_id=25,
            category_name="Asteroid",
        )
        self.salvage = _ensure_type(
            type_id=25588,
            name="Scorched Telemetry Processor",
            group_id=754,
            group_name="Salvaged Materials",
            category_id=4,
            category_name="Material",
        )
        EveMarketItemLocationPrice.objects.create(
            location=self.baseline,
            item=self.p1,
            sell_price=Decimal("110"),
            buy_price=Decimal("100"),
            split_price=Decimal("105"),
        )
        EveMarketItemLocationPrice.objects.create(
            location=self.baseline,
            item=self.p2,
            sell_price=Decimal("10000"),
            buy_price=Decimal("9000"),
            split_price=Decimal("9500"),
        )
        BuybackAcceptedItem.objects.create(
            eve_type=self.ore, category=BuybackAcceptedItem.Category.ORE
        )
        BuybackAcceptedItem.objects.create(
            eve_type=self.p1, category=BuybackAcceptedItem.Category.P1
        )
        BuybackAcceptedItem.objects.create(
            eve_type=self.p2, category=BuybackAcceptedItem.Category.P2
        )
        EveBuybackSettings.load()

    def test_appraise_p1_and_p2_and_reject_ice(self):
        paste = "Water\t10\nCoolant\t2\nCompressed Blue Ice\t50"
        response = self.client.post(
            f"{BASE_URL}/appraise",
            data={"paste": paste},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["accepted_count"], 2)
        self.assertEqual(data["rejected_count"], 1)
        # Water: 100 * 0.9 * 10 = 900; Coolant: 9000 * 1.0 * 2 = 18000
        self.assertEqual(data["offer_total"], 18900.0)
        self.assertNotIn("janice_url", data)
        by_name = {line["name"]: line for line in data["lines"]}
        self.assertTrue(by_name["Water"]["accepted"])
        self.assertEqual(by_name["Water"]["rate"], 0.9)
        self.assertEqual(by_name["Water"]["jita_buy"], 100.0)
        self.assertEqual(by_name["Water"]["unit_price"], 90.0)
        self.assertTrue(by_name["Coolant"]["accepted"])
        self.assertEqual(by_name["Coolant"]["rate"], 1.0)
        self.assertEqual(by_name["Coolant"]["jita_buy"], 9000.0)
        self.assertFalse(by_name["Compressed Blue Ice"]["accepted"])

    @patch(
        "buyback.helpers.pricing.reprocess_output",
        return_value={"Tritanium": 100},
    )
    def test_appraise_ore_uses_history_when_jita_buy_missing(
        self, unused_mock_reprocess
    ):
        trit = _ensure_type(
            type_id=34,
            name="Tritanium",
            group_id=18,
            group_name="Mineral",
            category_id=4,
            category_name="Material",
        )
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=trit,
            date=date(2026, 7, 31),
            average=Decimal("4.00"),
            highest=Decimal("4.10"),
            lowest=Decimal("3.90"),
            volume=1_000_000,
        )
        # Baseline has no Tritanium location buy — production Jita case.
        response = self.client.post(
            f"{BASE_URL}/appraise",
            data={"paste": "Compressed Veldspar\t1000"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["accepted_count"], 1)
        self.assertEqual(data["offer_total"], 400.0)
        by_name = {line["name"]: line for line in data["lines"]}
        self.assertTrue(by_name["Compressed Veldspar"]["accepted"])

    @patch(
        "buyback.helpers.pricing.reprocess_output",
        return_value={"Tritanium": 100},
    )
    @patch(
        "buyback.helpers.appraise.get_baseline_buy_prices_by_name",
        return_value={"Tritanium": Decimal("4")},
    )
    def test_appraise_rejects_items_not_on_allowlist(
        self, unused_mock_minerals, unused_mock_reprocess
    ):
        paste = (
            "Compressed Veldspar\t10\n"
            "Veldspar\t10\n"
            "Scorched Telemetry Processor\t2\n"
            "Water\t5"
        )
        response = self.client.post(
            f"{BASE_URL}/appraise",
            data={"paste": paste},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        by_name = {line["name"]: line for line in data["lines"]}
        self.assertTrue(by_name["Compressed Veldspar"]["accepted"])
        self.assertTrue(by_name["Water"]["accepted"])
        self.assertIsNone(by_name["Compressed Veldspar"]["jita_buy"])
        self.assertFalse(by_name["Veldspar"]["accepted"])
        self.assertFalse(by_name["Scorched Telemetry Processor"]["accepted"])
        self.assertEqual(
            by_name["Veldspar"]["reject_reason"],
            "Item type is not accepted for buyback",
        )

    def test_settings_includes_other_jita_buy_and_accepted_items(self):
        response = self.client.get(f"{BASE_URL}/settings")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["rate_rules"]["other_jita_buy"], 1.0)
        self.assertEqual(data["exclusions"], [])
        names = {item["name"] for item in data["accepted_items"]}
        self.assertIn("Compressed Veldspar", names)
        self.assertIn("Water", names)
        self.assertNotIn("Scorched Telemetry Processor", names)
