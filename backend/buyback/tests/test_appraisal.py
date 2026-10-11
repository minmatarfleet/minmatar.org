"""Tests for buyback paste parse, classify, price, and appraise endpoint."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase

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
from buyback.tests.helpers import BASE_URL, ensure_type
from eveonline.models import EveLocation
from industry.models import IndustryProduct
from market.models import EveMarketItemHistory, EveMarketItemLocationPrice


def _ensure_type(**kwargs):
    return ensure_type(**kwargs)


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
            classify_eve_type(self.p2).category, BuybackCategory.P2
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
    def test_merge_rate_rules_includes_demand_surplus(self):
        rules = merge_rate_rules({})
        self.assertEqual(rules["demand_jita_buy"], 1.0)
        self.assertEqual(rules["surplus_jita_buy"], 0.9)
        self.assertEqual(
            set(rules), {"ore_refine", "demand_jita_buy", "surplus_jita_buy"}
        )

    def test_merge_rate_rules_legacy_fallback(self):
        rules = merge_rate_rules(
            {"other_jita_buy": 0.95, "p1_jita_buy_cap": 0.8}
        )
        self.assertEqual(rules["demand_jita_buy"], 0.95)
        self.assertEqual(rules["surplus_jita_buy"], 0.8)
        self.assertNotIn("other_jita_buy", rules)
        self.assertNotIn("p1_jita_buy_cap", rules)

    def test_merge_rate_rules_new_keys_win(self):
        rules = merge_rate_rules(
            {
                "demand_jita_buy": 1.0,
                "surplus_jita_buy": 0.85,
                "other_jita_buy": 0.5,
                "p1_jita_buy_cap": 0.5,
            }
        )
        self.assertEqual(rules["demand_jita_buy"], 1.0)
        self.assertEqual(rules["surplus_jita_buy"], 0.85)

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

    @patch("buyback.helpers.pricing.ore_materials_per_portion")
    def test_price_ore_uses_mineral_buys(self, mock_per_portion):
        mock_per_portion.return_value = {"Tritanium": 1000, "Pyerite": 100}
        line = price_ore_line(
            name="Compressed Veldspar",
            quantity=100,
            type_id=62516,
            refine_rate=1.0,
            jita_share=1.0,
            mineral_buy_by_name={
                "Tritanium": Decimal("4"),
                "Pyerite": Decimal("20"),
            },
        )
        self.assertTrue(line.accepted)
        # 1000*4 + 100*20 = 6000
        self.assertEqual(line.line_total, 6000.0)
        self.assertEqual(line.jita_buy, 60.0)
        mock_per_portion.assert_called_once_with("Compressed Veldspar")

    @patch("buyback.helpers.pricing.ore_materials_per_portion")
    def test_price_ore_prorates_stacks_under_100(self, mock_per_portion):
        mock_per_portion.return_value = {"Tritanium": 400}
        line = price_ore_line(
            name="Compressed Veldspar",
            quantity=43,
            type_id=62516,
            refine_rate=1.0,
            jita_share=1.0,
            mineral_buy_by_name={"Tritanium": Decimal("5")},
        )
        self.assertTrue(line.accepted)
        # 43/100 * 400 Trit * 5 ISK = 860
        self.assertEqual(line.line_total, 860.0)

    @patch("buyback.helpers.pricing.ore_materials_per_portion")
    def test_price_ore_clamps_to_cheaper_ore_buy(self, mock_per_portion):
        mock_per_portion.return_value = {"Tritanium": 1000}
        line = price_ore_line(
            name="Compressed Veldspar",
            quantity=100,
            type_id=62516,
            refine_rate=1.0,
            jita_share=1.0,
            mineral_buy_by_name={"Tritanium": Decimal("4")},
            ore_unit_buy=Decimal("30"),
        )
        self.assertTrue(line.accepted)
        self.assertEqual(line.line_total, 3000.0)
        self.assertEqual(line.jita_buy, 30.0)
        self.assertEqual(line.unit_price, 30.0)

    @patch("buyback.helpers.pricing.ore_materials_per_portion")
    def test_price_ore_keeps_minerals_when_ore_buy_is_higher(
        self, mock_per_portion
    ):
        mock_per_portion.return_value = {"Tritanium": 1000}
        line = price_ore_line(
            name="Compressed Veldspar",
            quantity=100,
            type_id=62516,
            refine_rate=1.0,
            jita_share=0.9,
            mineral_buy_by_name={"Tritanium": Decimal("4")},
            ore_unit_buy=Decimal("80"),
        )
        self.assertTrue(line.accepted)
        # minerals 4000 < ore 8000; surplus 0.9 → 3600
        self.assertEqual(line.line_total, 3600.0)
        self.assertEqual(line.jita_buy, 40.0)
        self.assertEqual(line.unit_price, 36.0)


class BaselineBuyPriceHistoryTestCase(TestCase):
    def setUp(self):
        EveLocation.objects.create(
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
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.trit,
            date=date(2026, 7, 31),
            average=Decimal("3.93"),
            highest=Decimal("3.94"),
            lowest=Decimal("3.89"),
            volume=1_000_000,
        )
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.water,
            date=date(2026, 7, 31),
            average=Decimal("100.00"),
            highest=Decimal("110.00"),
            lowest=Decimal("90.00"),
            volume=50_000,
        )

    def test_uses_region_history_average_when_no_live_buy(self):
        prices = get_baseline_buy_prices([self.trit.id, self.water.id])
        self.assertEqual(prices[self.trit.id], Decimal("3.93"))
        self.assertEqual(prices[self.water.id], Decimal("100.00"))

        by_name = get_baseline_buy_prices_by_name(["Tritanium", "Water"])
        self.assertEqual(by_name["Tritanium"], Decimal("3.93"))
        self.assertEqual(by_name["Water"], Decimal("100.00"))

    def test_prefers_live_jita_buy_over_history(self):
        baseline = EveLocation.objects.get(price_baseline=True)
        EveMarketItemLocationPrice.objects.create(
            location=baseline,
            item=self.trit,
            sell_price=Decimal("4.00"),
            buy_price=Decimal("3.50"),
            split_price=Decimal("3.75"),
        )
        prices = get_baseline_buy_prices([self.trit.id, self.water.id])
        self.assertEqual(prices[self.trit.id], Decimal("3.50"))
        self.assertEqual(prices[self.water.id], Decimal("100.00"))

    def test_live_split_when_buy_missing(self):
        baseline = EveLocation.objects.get(price_baseline=True)
        EveMarketItemLocationPrice.objects.create(
            location=baseline,
            item=self.water,
            sell_price=Decimal("110.00"),
            buy_price=None,
            split_price=Decimal("105.00"),
        )
        prices = get_baseline_buy_prices([self.water.id])
        self.assertEqual(prices[self.water.id], Decimal("105.00"))


class AppraiseEndpointTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.baseline = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=10000002,
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
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.p1,
            date=date(2026, 7, 31),
            average=Decimal("100.00"),
            highest=Decimal("110.00"),
            lowest=Decimal("90.00"),
            volume=50_000,
        )
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.p2,
            date=date(2026, 7, 31),
            average=Decimal("9000.00"),
            highest=Decimal("10000.00"),
            lowest=Decimal("8000.00"),
            volume=10_000,
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
        # No recent-order demand → surplus rate 0.9 for both.
        # Water: 100 * 0.9 * 10 = 900; Coolant: 9000 * 0.9 * 2 = 16200
        self.assertEqual(data["offer_total"], 17100.0)
        self.assertNotIn("janice_url", data)
        by_name = {line["name"]: line for line in data["lines"]}
        self.assertTrue(by_name["Water"]["accepted"])
        self.assertEqual(by_name["Water"]["rate"], 0.9)
        self.assertEqual(by_name["Water"]["rate_reason"], "accepted_surplus")
        self.assertEqual(by_name["Water"]["jita_buy"], 100.0)
        self.assertEqual(by_name["Water"]["unit_price"], 90.0)
        self.assertTrue(by_name["Coolant"]["accepted"])
        self.assertEqual(by_name["Coolant"]["rate"], 0.9)
        self.assertEqual(by_name["Coolant"]["jita_buy"], 9000.0)
        self.assertFalse(by_name["Compressed Blue Ice"]["accepted"])

    @patch(
        "buyback.helpers.pricing._prorated_refine_outputs",
        return_value={"Tritanium": 100.0},
    )
    def test_appraise_ore_uses_region_history(self, unused_mock_refine):
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
        response = self.client.post(
            f"{BASE_URL}/appraise",
            data={"paste": "Compressed Veldspar\t1000"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["accepted_count"], 1)
        # Tritanium not in demand → surplus 0.9 × 400.
        self.assertEqual(data["offer_total"], 360.0)
        by_name = {line["name"]: line for line in data["lines"]}
        self.assertTrue(by_name["Compressed Veldspar"]["accepted"])
        self.assertEqual(by_name["Compressed Veldspar"]["rate"], 0.9)

    @patch(
        "buyback.helpers.pricing._prorated_refine_outputs",
        return_value={"Tritanium": 100.0},
    )
    @patch(
        "buyback.helpers.appraise.get_baseline_buy_prices_by_name",
        return_value={"Tritanium": Decimal("4")},
    )
    def test_appraise_rejects_items_not_on_allowlist(
        self, unused_mock_minerals, unused_mock_refine
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
        self.assertEqual(by_name["Compressed Veldspar"]["jita_buy"], 40.0)
        self.assertFalse(by_name["Veldspar"]["accepted"])
        self.assertFalse(by_name["Scorched Telemetry Processor"]["accepted"])
        self.assertEqual(
            by_name["Veldspar"]["reject_reason"],
            "Item type is not accepted for buyback",
        )

    def test_settings_includes_demand_surplus_and_accepted_items(self):
        response = self.client.get(f"{BASE_URL}/settings")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["rate_rules"]["demand_jita_buy"], 1.0)
        self.assertEqual(data["rate_rules"]["surplus_jita_buy"], 0.9)
        self.assertEqual(data["exclusions"], [])
        names = {item["name"] for item in data["accepted_items"]}
        self.assertIn("Compressed Veldspar", names)
        self.assertIn("Water", names)
        self.assertNotIn("Scorched Telemetry Processor", names)
        water = next(
            item for item in data["accepted_items"] if item["name"] == "Water"
        )
        self.assertIn("in_demand", water)
        self.assertFalse(water["in_demand"])

    def test_settings_accepted_items_include_used_in(self):
        product = _ensure_type(
            type_id=999002,
            name="Used-In Hull",
            group_id=25,
            group_name="Frigate",
            category_id=6,
            category_name="Ship",
        )
        IndustryProduct.objects.create(
            eve_type=product,
            strategy="imported",
            breakdown={
                "name": "Used-In Hull",
                "type_id": product.id,
                "quantity": 1,
                "children": [
                    {
                        "name": "Water",
                        "type_id": self.p1.id,
                        "quantity": 10,
                        "children": [],
                    },
                    {
                        "name": "Coolant",
                        "type_id": self.p2.id,
                        "quantity": 2,
                        "children": [],
                    },
                ],
            },
        )
        response = self.client.get(f"{BASE_URL}/settings")
        self.assertEqual(response.status_code, 200)
        by_name = {
            item["name"]: item for item in response.json()["accepted_items"]
        }
        water_used = {entry["name"] for entry in by_name["Water"]["used_in"]}
        coolant_used = {
            entry["name"] for entry in by_name["Coolant"]["used_in"]
        }
        self.assertIn("Used-In Hull", water_used)
        self.assertIn("Used-In Hull", coolant_used)
