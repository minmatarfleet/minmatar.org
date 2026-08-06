from datetime import timedelta
from unittest.mock import patch

from django.test import Client
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from eveonline.models import EveLocation
from fittings.models import EveFitting
from market.helpers.ops_monitor import build_ops_monitor
from market.helpers.readiness import (
    doctrine_readiness,
    fitting_readiness,
    shortfall,
)
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketInferredSale,
)
from market.models.item import EveMarketItemExpectation, EveMarketItemOrder

BASE_URL = "/api/market"


class ReadinessHelperTestCase(TestCase):
    def test_fitting_readiness_levels(self):
        self.assertEqual(fitting_readiness(0, 10), "empty")
        self.assertEqual(fitting_readiness(5, 10), "thin")
        self.assertEqual(fitting_readiness(10, 10), "ready")
        self.assertEqual(fitting_readiness(3, None), "unknown")

    def test_doctrine_readiness_aggregate(self):
        self.assertEqual(doctrine_readiness([(10, 10), (5, 5)]), "ready")
        self.assertEqual(doctrine_readiness([(0, 10), (0, 5)]), "empty")
        self.assertEqual(doctrine_readiness([(0, 10), (5, 5)]), "thin")
        self.assertEqual(doctrine_readiness([(1, None)]), "unknown")

    def test_shortfall(self):
        self.assertEqual(shortfall(3, 10), 7)
        self.assertEqual(shortfall(12, 10), 0)


class OpsMonitorApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        super().setUp()
        self.loc = EveLocation.objects.create(
            location_id=99,
            location_name="Somewhere",
            short_name="Somewhere",
            solar_system_id=1,
            solar_system_name="Somewhere",
            market_active=True,
        )
        self.fit = EveFitting.objects.create(
            name="[NVY-5] Atron",
            ship_id=608,
            description="Testing",
            eft_format="[Atron, [NVY-5] Atron]",
        )
        EveMarketContractExpectation.objects.create(
            fitting=self.fit,
            location=self.loc,
            quantity=4,
        )
        EveMarketContract.objects.create(
            id=1,
            status="outstanding",
            title="Bad Title",
            price=1,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            match_score=0.5,
            match_is_flagged=False,
        )

    def test_ops_monitor_is_public(self):
        response = self.client.get(f"{BASE_URL}/ops-monitor")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("understocked_contracts", data)
        self.assertIn("sell_gaps", data)

    def test_build_ops_monitor_queues(self):
        data = build_ops_monitor(location_id=self.loc.location_id)
        self.assertGreaterEqual(data["summary"]["understocked_contracts"], 1)
        self.assertNotIn("mismatched_contracts", data)
        self.assertIsNotNone(data["summary"]["contracts_health_pct"])
        self.assertIn("sell_orders_health_pct", data["summary"])
        self.assertIn("overall_health_pct", data["summary"])
        self.assertEqual(data["summary"]["contract_targets"], 1)
        self.assertEqual(data["summary"]["contract_fulfilled"], 0)
        self.assertIn("total_isk_on_market", data["summary"])
        self.assertGreaterEqual(data["summary"]["contracts_isk"], 0)
        self.assertGreaterEqual(data["summary"]["sell_orders_isk"], 0)

    def test_understocked_contracts_sorted_by_ship_size(self):
        ship_cat, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        frigate_grp, _ = EveGroup.objects.get_or_create(
            id=25,
            defaults={
                "name": "Frigate",
                "published": True,
                "eve_category": ship_cat,
            },
        )
        battleship_grp, _ = EveGroup.objects.get_or_create(
            id=27,
            defaults={
                "name": "Battleship",
                "published": True,
                "eve_category": ship_cat,
            },
        )
        EveType.objects.update_or_create(
            id=608,
            defaults={
                "name": "Atron",
                "published": True,
                "eve_group": frigate_grp,
            },
        )
        EveType.objects.update_or_create(
            id=24692,
            defaults={
                "name": "Abaddon",
                "published": True,
                "eve_group": battleship_grp,
            },
        )
        # Existing fit is Atron (frigate); add a battleship expectation.
        bs_fit = EveFitting.objects.create(
            name="[NVY-5] Abaddon",
            ship_id=24692,
            description="Testing",
            eft_format="[Abaddon, [NVY-5] Abaddon]",
        )
        EveMarketContractExpectation.objects.create(
            fitting=bs_fit,
            location=self.loc,
            quantity=2,
        )

        data = build_ops_monitor(location_id=self.loc.location_id)
        ship_ids = [row["ship_id"] for row in data["understocked_contracts"]]
        self.assertEqual(ship_ids, [608, 24692])

    def test_sell_gaps_include_useful_ship_icons(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=800,
            defaults={
                "name": "Projectile Ammo",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        for type_id, name in (
            (12614, "Fusion S"),
            (28668, "Nanite Repair Paste"),
        ):
            EveType.objects.update_or_create(
                id=type_id,
                defaults={
                    "name": name,
                    "published": True,
                    "eve_group": charge_grp,
                },
            )
        self.fit.eft_format = (
            "[Rifter, [NVY-5] Atron]\n\n"
            "Nanite Repair Paste x5\n"
            "Fusion S x2000\n"
        )
        self.fit.ship_id = 587
        self.fit.save()

        data = build_ops_monitor(location_id=self.loc.location_id)
        fusion = next(
            (
                row
                for row in data["sell_gaps"]
                if row["item_name"] == "Fusion S"
            ),
            None,
        )
        self.assertIsNotNone(fusion)
        self.assertEqual(
            fusion["ships"],
            [{"ship_id": 587, "fitting_name": "[NVY-5] Atron"}],
        )

    def test_sell_gaps_ships_can_exceed_ui_cap(self):
        """Many doctrine hulls for one consumable → UI shows 10 icons +N."""
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=800,
            defaults={
                "name": "Projectile Ammo",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        EveType.objects.update_or_create(
            id=28668,
            defaults={
                "name": "Nanite Repair Paste",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        # 12 distinct hulls → frontend max=10 renders +2 circle.
        for i in range(12):
            fit = EveFitting.objects.create(
                name=f"[NVY-5] Hull {i}",
                ship_id=600 + i,
                description="Testing",
                eft_format=f"[Ship, Hull {i}]\n\nNanite Repair Paste x5\n",
            )
            EveMarketContractExpectation.objects.create(
                fitting=fit,
                location=self.loc,
                quantity=1,
            )

        data = build_ops_monitor(location_id=self.loc.location_id)
        nanite = next(
            (
                row
                for row in data["sell_gaps"]
                if row["item_name"] == "Nanite Repair Paste"
            ),
            None,
        )
        self.assertIsNotNone(nanite)
        self.assertGreaterEqual(len(nanite["ships"]), 12)

    def test_ops_monitor_unknown_location_returns_empty_queues(self):
        """Unknown location_id filters to no locations — empty monitor, not all locations."""
        response = self.client.get(
            f"{BASE_URL}/ops-monitor",
            {"location_id": 9999999999999},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["understocked_contracts"], [])
        self.assertEqual(data["sell_gaps"], [])
        self.assertEqual(data["summary"]["understocked_contracts"], 0)
        self.assertEqual(data["summary"]["sell_gaps"], 0)

    def test_sell_gaps_summary_returns_full_list(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        for i in range(105):
            type_id = 90000 + i
            EveType.objects.update_or_create(
                id=type_id,
                defaults={
                    "name": f"Gap Item {i}",
                    "published": True,
                    "eve_group": charge_grp,
                },
            )
            EveMarketItemExpectation.objects.create(
                item_id=type_id,
                location=self.loc,
                quantity=100,
            )

        data = build_ops_monitor(location_id=self.loc.location_id)
        self.assertEqual(len(data["sell_gaps"]), 105)
        self.assertEqual(data["summary"]["sell_gaps"], 105)
        for row in data["sell_gaps"]:
            self.assertTrue(row["coverage_gap"])
            self.assertTrue(row["viability_gap"])
            self.assertEqual(row["item_type"], "consumable")
            self.assertEqual(row["units_1d"], 0)
            self.assertEqual(row["units_3d"], 0)
            self.assertEqual(row["weekly_units"], 0)
            self.assertEqual(row["units_30d"], 0)
            self.assertEqual(row["units_90d"], 0)
            self.assertIsNone(row["avg_markup_pct"])

    def test_viability_only_gap_when_listed_but_overpriced(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        item, _ = EveType.objects.update_or_create(
            id=91010,
            defaults={
                "name": "Viability Only Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=100,
        )
        # Coverage OK (100 listed) but only 11 at a viable price.
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=11,
            price=2_200_000,
            is_buy_order=False,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=89,
            price=3_000_000,
            is_buy_order=False,
        )

        with patch(
            "market.helpers.ops_monitor.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            data = build_ops_monitor(location_id=self.loc.location_id)

        gap = next(
            row
            for row in data["sell_gaps"]
            if row["item_name"] == "Viability Only Ammo"
        )
        self.assertEqual(gap["current_quantity"], 100)
        self.assertEqual(gap["viable_quantity"], 11)
        self.assertFalse(gap["coverage_gap"])
        self.assertTrue(gap["viability_gap"])
        self.assertEqual(gap["item_type"], "consumable")

    def test_both_gaps_when_stock_is_thin(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        item, _ = EveType.objects.update_or_create(
            id=91011,
            defaults={
                "name": "Thin Stock Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=100,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=10,
            price=2_000_000,
            is_buy_order=False,
        )

        with patch(
            "market.helpers.ops_monitor.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            data = build_ops_monitor(location_id=self.loc.location_id)

        gap = next(
            row
            for row in data["sell_gaps"]
            if row["item_name"] == "Thin Stock Ammo"
        )
        self.assertTrue(gap["coverage_gap"])
        self.assertTrue(gap["viability_gap"])
        self.assertEqual(gap["item_type"], "consumable")

    def test_gap_row_includes_volume_windows_and_markup(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        item, _ = EveType.objects.update_or_create(
            id=91020,
            defaults={
                "name": "Weekly Sold Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=100,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=40,
            price=3_000_000,
            is_buy_order=False,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=10,
            price=6_000_000,
            is_buy_order=False,
        )
        now = timezone.now()
        EveMarketInferredSale.objects.create(
            location=self.loc,
            item=item,
            quantity=30,
            price=1_000_000,
            inferred_at=now - timedelta(hours=12),
            reason=EveMarketInferredSale.REASON_SELLOUT,
        )
        EveMarketInferredSale.objects.create(
            location=self.loc,
            item=item,
            quantity=4,
            price=1_000_000,
            inferred_at=now - timedelta(days=2),
            reason=EveMarketInferredSale.REASON_PARTIAL_FILL,
        )
        EveMarketInferredSale.objects.create(
            location=self.loc,
            item=item,
            quantity=12,
            price=1_000_000,
            inferred_at=now - timedelta(days=6),
            reason=EveMarketInferredSale.REASON_PARTIAL_FILL,
        )
        EveMarketInferredSale.objects.create(
            location=self.loc,
            item=item,
            quantity=8,
            price=1_000_000,
            inferred_at=now - timedelta(days=20),
            reason=EveMarketInferredSale.REASON_SELLOUT,
        )
        EveMarketInferredSale.objects.create(
            location=self.loc,
            item=item,
            quantity=5,
            price=1_000_000,
            inferred_at=now - timedelta(days=60),
            reason=EveMarketInferredSale.REASON_SELLOUT,
        )
        # Older than the 90-day window: excluded.
        EveMarketInferredSale.objects.create(
            location=self.loc,
            item=item,
            quantity=999,
            price=1_000_000,
            inferred_at=now - timedelta(days=120),
            reason=EveMarketInferredSale.REASON_SELLOUT,
        )

        with patch(
            "market.helpers.ops_monitor.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            data = build_ops_monitor(location_id=self.loc.location_id)

        gap = next(
            row
            for row in data["sell_gaps"]
            if row["item_name"] == "Weekly Sold Ammo"
        )
        self.assertEqual(gap["units_1d"], 30)
        self.assertEqual(gap["units_3d"], 34)
        self.assertEqual(gap["weekly_units"], 46)
        self.assertEqual(gap["units_30d"], 54)
        self.assertEqual(gap["units_90d"], 59)
        # qty-weighted avg price = (40*3M + 10*6M) / 50 = 3.6M → +80% vs 2M
        self.assertEqual(gap["avg_markup_pct"], 80.0)
        # 50 listed ÷ (46/7 per day) ≈ 7.6 days of stock
        self.assertEqual(gap["days_of_stock"], 7.6)
        self.assertEqual(
            gap["flags"],
            ["understocked", "overpriced"],
        )

    def test_days_of_stock_null_without_recent_sales(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        item, _ = EveType.objects.update_or_create(
            id=91021,
            defaults={
                "name": "No Sales Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=100,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=20,
            price=2_000_000,
            is_buy_order=False,
        )

        with patch(
            "market.helpers.ops_monitor.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            data = build_ops_monitor(location_id=self.loc.location_id)

        gap = next(
            row
            for row in data["sell_gaps"]
            if row["item_name"] == "No Sales Ammo"
        )
        self.assertIsNone(gap["days_of_stock"])
        self.assertEqual(gap["flags"], ["understocked"])

    def test_seven_day_vwap_avoids_one_day_dip_false_overpriced(self):
        """Listing fair vs 7d VWAP is not overpriced even if latest-day dipped."""
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        item, _ = EveType.objects.update_or_create(
            id=91022,
            defaults={
                "name": "Smoothed Baseline Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=100,
        )
        # Listed at 2.0M — fair vs 2.0M 7d VWAP, but +100% vs a 1.0M one-day dip.
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=100,
            price=2_000_000,
            is_buy_order=False,
        )

        with (
            patch(
                "market.helpers.ops_monitor.get_volume_weighted_average_by_type_id",
                return_value={item.pk: 2_000_000},
            ),
            patch(
                "market.helpers.ops_monitor.get_prices_by_type_id",
                return_value={item.pk: 1_000_000},
            ),
        ):
            data = build_ops_monitor(location_id=self.loc.location_id)

        self.assertEqual(
            [row["item_name"] for row in data["sell_gaps"]],
            [],
        )
        self.assertEqual(data["summary"]["sell_orders_viability_pct"], 100.0)

    def test_overstocked_overpriced_flags_on_viability_gap(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        item, _ = EveType.objects.update_or_create(
            id=91023,
            defaults={
                "name": "Fat Overpriced Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=50,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=120,
            price=3_000_000,
            is_buy_order=False,
        )

        with patch(
            "market.helpers.ops_monitor.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            data = build_ops_monitor(location_id=self.loc.location_id)

        gap = next(
            row
            for row in data["sell_gaps"]
            if row["item_name"] == "Fat Overpriced Ammo"
        )
        self.assertFalse(gap["coverage_gap"])
        self.assertTrue(gap["viability_gap"])
        self.assertEqual(gap["avg_markup_pct"], 50.0)
        self.assertEqual(
            gap["flags"],
            ["overstocked", "overpriced"],
        )

    def test_understocked_contracts_summary_matches_list_cap(self):
        for i in range(55):
            fit = EveFitting.objects.create(
                name=f"[NVY-5] Hull {i}",
                ship_id=700 + i,
                description="Testing",
                eft_format=f"[Ship, Hull {i}]",
            )
            EveMarketContractExpectation.objects.create(
                fitting=fit,
                location=self.loc,
                quantity=4,
            )

        data = build_ops_monitor(location_id=self.loc.location_id)
        self.assertEqual(len(data["understocked_contracts"]), 50)
        self.assertEqual(data["summary"]["understocked_contracts"], 50)

    def test_overpriced_stock_counts_as_coverage_not_viability(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        item, _ = EveType.objects.update_or_create(
            id=91001,
            defaults={
                "name": "Viable Gap Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=100,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=11,
            price=2_200_000,
            is_buy_order=False,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=89,
            price=3_000_000,
            is_buy_order=False,
        )

        with patch(
            "market.helpers.ops_monitor.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            data = build_ops_monitor(location_id=self.loc.location_id)

        gap = next(
            row
            for row in data["sell_gaps"]
            if row["item_name"] == "Viable Gap Ammo"
        )
        self.assertEqual(gap["current_quantity"], 100)
        self.assertEqual(gap["viable_quantity"], 11)
        self.assertEqual(gap["shortfall"], 89)
        self.assertFalse(gap["coverage_gap"])
        self.assertTrue(gap["viability_gap"])
        self.assertEqual(gap["item_type"], "consumable")
        self.assertEqual(data["summary"]["sell_order_targets"], 1)
        self.assertEqual(data["summary"]["sell_order_fulfilled"], 1)
        self.assertEqual(data["summary"]["sell_order_viable_fulfilled"], 0)
        self.assertEqual(data["summary"]["sell_orders_health_pct"], 100.0)
        self.assertEqual(data["summary"]["sell_orders_viability_pct"], 11.0)
        self.assertEqual(data["summary"]["sell_gaps"], 1)
        self.assertEqual(gap["flags"], ["overpriced"])
        self.assertIsNone(gap["days_of_stock"])

    def test_boundary_price_counts_as_viable(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        item, _ = EveType.objects.update_or_create(
            id=91002,
            defaults={
                "name": "Boundary Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=100,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=100,
            price=2_400_000,
            is_buy_order=False,
        )

        with patch(
            "market.helpers.ops_monitor.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            data = build_ops_monitor(location_id=self.loc.location_id)

        self.assertEqual(
            [row["item_name"] for row in data["sell_gaps"]],
            [],
        )
        self.assertEqual(data["summary"]["sell_orders_health_pct"], 100.0)
        self.assertEqual(data["summary"]["sell_orders_viability_pct"], 100.0)
        self.assertEqual(data["summary"]["sell_order_viable_fulfilled"], 1)

    def test_missing_baseline_keeps_listed_stock_viable(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        item, _ = EveType.objects.update_or_create(
            id=91003,
            defaults={
                "name": "No Baseline Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=100,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=100,
            price=50_000_000,
            is_buy_order=False,
        )

        with patch(
            "market.helpers.ops_monitor.get_prices_by_type_id",
            return_value={},
        ):
            data = build_ops_monitor(location_id=self.loc.location_id)

        self.assertEqual(data["sell_gaps"], [])
        self.assertEqual(data["summary"]["sell_orders_viability_pct"], 100.0)
        self.assertEqual(data["summary"]["sell_order_viable_fulfilled"], 1)

    def test_cheap_baseline_counts_overpriced_orders(self):
        charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        charge_grp, _ = EveGroup.objects.get_or_create(
            id=801,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": charge_cat,
            },
        )
        item, _ = EveType.objects.update_or_create(
            id=91004,
            defaults={
                "name": "Cheap Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=100,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=100,
            price=900_000,
            is_buy_order=False,
        )

        with patch(
            "market.helpers.ops_monitor.get_prices_by_type_id",
            return_value={item.pk: 50_000},
        ):
            data = build_ops_monitor(location_id=self.loc.location_id)

        self.assertEqual(data["sell_gaps"], [])
        self.assertEqual(data["summary"]["sell_orders_viability_pct"], 100.0)
