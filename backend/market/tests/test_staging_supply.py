from datetime import timedelta
from unittest.mock import patch

from django.test import Client
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from eveonline.models import EveLocation
from fittings.models import EveFitting
from market.helpers.contract_health import build_contract_health
from market.helpers.health_common import sell_gap_flags
from market.helpers.sell_order_health import build_sell_order_health
from market.helpers.health_snapshot import (
    record_contract_health_snapshots,
    record_sell_order_health_snapshots,
)
from market.helpers.readiness import (
    doctrine_readiness,
    fitting_readiness,
    shortfall,
)
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketContractItem,
    EveMarketInferredSale,
)
from market.models.item import EveMarketItemExpectation, EveMarketItemOrder

BASE_URL = "/api/market"


def _contract_at(location_id: int) -> dict:
    return build_contract_health(location_id=location_id)["by_location"][
        location_id
    ]


def _sell_at(location_id: int) -> dict:
    return build_sell_order_health(location_id=location_id)["by_location"][
        location_id
    ]


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


class MarketHealthApiTestCase(TestCase):
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

    def test_market_health_is_public(self):
        record_contract_health_snapshots(location_id=self.loc.location_id)
        record_sell_order_health_snapshots(location_id=self.loc.location_id)
        response = self.client.get(
            f"{BASE_URL}/health",
            {"location_id": self.loc.location_id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("contracts", data)
        self.assertIn("sell_orders", data)
        self.assertIn("latest", data["contracts"])
        self.assertIn("history", data["contracts"])

    def test_build_contract_and_sell_health_queues(self):
        contracts = _contract_at(self.loc.location_id)
        sells = _sell_at(self.loc.location_id)
        # Outstanding contract satisfies presence desired=1 → ready, omitted.
        self.assertEqual(contracts["rows"], [])
        self.assertNotIn("mismatched_contracts", contracts)
        self.assertIsNotNone(contracts["summary"]["health_pct"])
        self.assertIn("viability_pct", contracts["summary"])
        self.assertIn("viable_fulfilled", contracts["summary"])
        self.assertIn("health_pct", sells["summary"])
        self.assertEqual(contracts["summary"]["targets"], 1)
        self.assertEqual(contracts["summary"]["fulfilled"], 1)
        self.assertGreaterEqual(contracts["summary"]["isk"], 0)
        self.assertGreaterEqual(sells["summary"]["isk"], 0)

    def test_contract_viability_counts_fair_prices_only(self):
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
        EveType.objects.update_or_create(
            id=608,
            defaults={
                "name": "Atron",
                "published": True,
                "eve_group": frigate_grp,
            },
        )
        # Replace the default understocked setup with a fully stocked target.
        EveMarketContractExpectation.objects.filter(location=self.loc).delete()
        EveMarketContract.objects.filter(location=self.loc).delete()
        EveMarketContractExpectation.objects.create(
            fitting=self.fit,
            location=self.loc,
            quantity=2,
        )
        fair = EveMarketContract.objects.create(
            id=101,
            status="outstanding",
            title="Fair Atron",
            price=1_000_000,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            items_fetched=True,
            match_score=1.0,
        )
        over = EveMarketContract.objects.create(
            id=102,
            status="outstanding",
            title="Overpriced Atron",
            price=2_000_000,
            issuer_external_id=2,
            location=self.loc,
            fitting=self.fit,
            items_fetched=True,
            match_score=1.0,
        )
        for contract in (fair, over):
            EveMarketContractItem.objects.create(
                contract=contract,
                type_id=608,
                quantity=1,
                is_included=True,
            )

        with patch(
            "market.helpers.contract_health.forge_baseline_by_type",
            return_value={608: 1_000_000},
        ):
            contracts = _contract_at(self.loc.location_id)
            _sell_at(self.loc.location_id)

        self.assertEqual(contracts["summary"]["targets"], 1)
        self.assertEqual(contracts["summary"]["fulfilled"], 1)
        self.assertEqual(contracts["summary"]["viable_fulfilled"], 0)
        self.assertEqual(contracts["summary"]["health_pct"], 100.0)
        # One of two contracts is within +20% of 1M contents baseline → 50%
        self.assertEqual(contracts["summary"]["viability_pct"], 50.0)
        self.assertEqual(contracts["rows"], [])

    def test_contract_viability_uses_actual_contents(self):
        """Upgraded modules raise the contents baseline and can make asks viable."""
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
        module_cat, _ = EveCategory.objects.get_or_create(
            id=7, defaults={"name": "Module", "published": True}
        )
        module_grp, _ = EveGroup.objects.get_or_create(
            id=55,
            defaults={
                "name": "Energy Weapon",
                "published": True,
                "eve_category": module_cat,
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
            id=2048,
            defaults={
                "name": "Damage Control II",
                "published": True,
                "eve_group": module_grp,
            },
        )
        EveMarketContractExpectation.objects.filter(location=self.loc).delete()
        EveMarketContract.objects.filter(location=self.loc).delete()
        EveMarketContractExpectation.objects.create(
            fitting=self.fit,
            location=self.loc,
            quantity=1,
        )
        # Ask is 50% over bare hull EFT, but within +20% of hull+module contents.
        contract = EveMarketContract.objects.create(
            id=201,
            status="outstanding",
            title="Upgraded Atron",
            price=1_500_000,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            items_fetched=True,
            match_score=0.95,
        )
        EveMarketContractItem.objects.create(
            contract=contract, type_id=608, quantity=1, is_included=True
        )
        EveMarketContractItem.objects.create(
            contract=contract, type_id=2048, quantity=1, is_included=True
        )

        with patch(
            "market.helpers.contract_health.forge_baseline_by_type",
            return_value={608: 1_000_000, 2048: 400_000},
        ):
            contracts = _contract_at(self.loc.location_id)

        # Contents baseline 1.4M → cap 1.68M; 1.5M ask is viable.
        self.assertEqual(contracts["summary"]["viable_fulfilled"], 1)
        self.assertEqual(contracts["summary"]["viability_pct"], 100.0)

    def test_contract_viability_ignores_unstocked_targets(self):
        """Empty doctrine lines drag coverage, not viability."""
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
        EveType.objects.update_or_create(
            id=608,
            defaults={
                "name": "Atron",
                "published": True,
                "eve_group": frigate_grp,
            },
        )
        EveMarketContractExpectation.objects.filter(location=self.loc).delete()
        EveMarketContract.objects.filter(location=self.loc).delete()
        EveMarketContractExpectation.objects.create(
            fitting=self.fit,
            location=self.loc,
            quantity=1,
        )
        empty_fit = EveFitting.objects.create(
            name="[NVY-5] Empty Hull",
            ship_id=609,
            description="Testing",
            eft_format="[Atron, Empty]",
        )
        EveMarketContractExpectation.objects.create(
            fitting=empty_fit,
            location=self.loc,
            quantity=1,
        )
        listed = EveMarketContract.objects.create(
            id=301,
            status="outstanding",
            title="Fair Atron",
            price=1_000_000,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            items_fetched=True,
            match_score=1.0,
        )
        EveMarketContractItem.objects.create(
            contract=listed, type_id=608, quantity=1, is_included=True
        )

        with patch(
            "market.helpers.contract_health.forge_baseline_by_type",
            return_value={608: 1_000_000},
        ):
            contracts = _contract_at(self.loc.location_id)

        self.assertEqual(contracts["summary"]["targets"], 2)
        self.assertEqual(contracts["summary"]["listed_targets"], 1)
        self.assertEqual(contracts["summary"]["health_pct"], 50.0)
        self.assertEqual(contracts["summary"]["viability_pct"], 100.0)
        self.assertEqual(contracts["summary"]["viable_fulfilled"], 1)

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

        contracts = _contract_at(self.loc.location_id)
        _sell_at(self.loc.location_id)
        # Atron has an outstanding contract → presence-ready → omitted.
        ship_ids = [row["ship_id"] for row in contracts["rows"]]
        self.assertEqual(ship_ids, [24692])

    def test_understocked_contracts_include_finished_volume_windows(self):
        now = timezone.now()
        # Remove outstanding stock so this fit is understocked (presence).
        EveMarketContract.objects.filter(
            id=1, location=self.loc, fitting=self.fit
        ).delete()
        EveMarketContract.objects.create(
            id=101,
            status="finished",
            title="Finished recent",
            price=1,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            completed_at=now - timedelta(hours=12),
        )
        EveMarketContract.objects.create(
            id=102,
            status="finished",
            title="Finished 2d",
            price=1,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            completed_at=now - timedelta(days=2),
        )
        EveMarketContract.objects.create(
            id=103,
            status="finished",
            title="Finished 6d",
            price=1,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            completed_at=now - timedelta(days=6),
        )
        EveMarketContract.objects.create(
            id=104,
            status="finished",
            title="Finished 20d",
            price=1,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            completed_at=now - timedelta(days=20),
        )
        EveMarketContract.objects.create(
            id=105,
            status="finished",
            title="Finished 60d",
            price=1,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            completed_at=now - timedelta(days=60),
        )
        # Outside 90d window.
        EveMarketContract.objects.create(
            id=106,
            status="finished",
            title="Finished old",
            price=1,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            completed_at=now - timedelta(days=120),
        )

        contracts = _contract_at(self.loc.location_id)
        _sell_at(self.loc.location_id)
        row = next(
            r for r in contracts["rows"] if r["fitting_id"] == self.fit.id
        )
        self.assertEqual(row["units_1d"], 1)
        self.assertEqual(row["units_3d"], 2)
        self.assertEqual(row["weekly_units"], 3)
        self.assertEqual(row["units_30d"], 4)
        self.assertEqual(row["units_90d"], 5)
        # No outstanding ÷ (3/7 per day) → 0 days of stock
        self.assertEqual(row["days_of_stock"], 0.0)
        self.assertGreaterEqual(contracts["summary"]["history_days"], 60)

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

        _contract_at(self.loc.location_id)
        sells = _sell_at(self.loc.location_id)
        fusion = next(
            (row for row in sells["rows"] if row["item_name"] == "Fusion S"),
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

        _contract_at(self.loc.location_id)
        sells = _sell_at(self.loc.location_id)
        nanite = next(
            (
                row
                for row in sells["rows"]
                if row["item_name"] == "Nanite Repair Paste"
            ),
            None,
        )
        self.assertIsNotNone(nanite)
        self.assertGreaterEqual(len(nanite["ships"]), 12)

    def test_market_health_unknown_location_returns_empty(self):
        """Unknown location_id has no snapshots — null latest, empty history."""
        response = self.client.get(
            f"{BASE_URL}/health",
            {"location_id": 9999999999999},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["contracts"]["latest"])
        self.assertEqual(data["contracts"]["history"], [])
        self.assertIsNone(data["sell_orders"]["latest"])
        self.assertEqual(data["sell_orders"]["history"], [])

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

        _contract_at(self.loc.location_id)
        sells = _sell_at(self.loc.location_id)
        self.assertEqual(len(sells["rows"]), 105)
        self.assertEqual(
            sum(
                1
                for r in sells["rows"]
                if r["coverage_gap"] or r["viability_gap"]
            ),
            105,
        )
        for row in sells["rows"]:
            self.assertTrue(row["coverage_gap"])
            self.assertFalse(row["viability_gap"])
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
        # Listed, but nothing at a viable price → viability gap only.
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=100,
            price=3_000_000,
            is_buy_order=False,
        )

        with patch(
            "market.helpers.health_common.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            _contract_at(self.loc.location_id)
            sells = _sell_at(self.loc.location_id)

        gap = next(
            row
            for row in sells["rows"]
            if row["item_name"] == "Viability Only Ammo"
        )
        self.assertEqual(gap["current_quantity"], 100)
        self.assertEqual(gap["viable_quantity"], 0)
        self.assertFalse(gap["coverage_gap"])
        self.assertTrue(gap["viability_gap"])
        self.assertEqual(gap["item_type"], "consumable")

    def test_no_gaps_when_any_fair_stock_is_listed(self):
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
            "market.helpers.health_common.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            _contract_at(self.loc.location_id)
            sells = _sell_at(self.loc.location_id)

        gap = next(
            row
            for row in sells["rows"]
            if row["item_name"] == "Thin Stock Ammo"
        )
        # Presence desired=1; any fair listing covers both gap kinds.
        self.assertFalse(gap["coverage_gap"])
        self.assertFalse(gap["viability_gap"])
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
            "market.helpers.health_common.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            _contract_at(self.loc.location_id)
            sells = _sell_at(self.loc.location_id)

        gap = next(
            row
            for row in sells["rows"]
            if row["item_name"] == "Weekly Sold Ammo"
        )
        self.assertEqual(gap["units_1d"], 30)
        self.assertEqual(gap["units_3d"], 34)
        self.assertEqual(gap["weekly_units"], 46)
        self.assertEqual(gap["units_30d"], 54)
        self.assertEqual(gap["units_90d"], 59)
        # qty-weighted avg price = (40*3M + 10*6M) / 50 = 3.6M → +80% vs 2M
        self.assertEqual(gap["avg_markup_pct"], 80.0)
        # 50 listed ÷ (46/7 per day) ≈ 7.6 days of stock (≥ 7 → in stock)
        self.assertEqual(gap["days_of_stock"], 7.6)
        self.assertEqual(
            gap["flags"],
            ["in_stock", "overpriced"],
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
            "market.helpers.health_common.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            _contract_at(self.loc.location_id)
            sells = _sell_at(self.loc.location_id)

        gap = next(
            row for row in sells["rows"] if row["item_name"] == "No Sales Ammo"
        )
        self.assertIsNone(gap["days_of_stock"])
        # No sales rate → cannot be understocked by days; still listed → in stock
        self.assertEqual(gap["flags"], ["in_stock"])

    def test_understocked_flag_when_under_seven_days_of_stock(self):
        self.assertEqual(
            sell_gap_flags(40, 100, None, 6.9),
            ["understocked"],
        )
        self.assertEqual(
            sell_gap_flags(40, 100, None, 7.0),
            ["in_stock"],
        )
        self.assertEqual(
            sell_gap_flags(0, 100, None, None),
            ["out_of_stock"],
        )
        self.assertEqual(
            sell_gap_flags(120, 50, 12.0, 3.0),
            ["understocked", "overpriced"],
        )
        # Presence targets do not emit overstocked from qty vs expected.
        self.assertEqual(
            sell_gap_flags(120, 1, None, None),
            ["in_stock"],
        )

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
                "market.helpers.health_common.get_volume_weighted_average_by_type_id",
                return_value={item.pk: 2_000_000},
            ),
            patch(
                "market.helpers.health_common.get_prices_by_type_id",
                return_value={item.pk: 1_000_000},
            ),
        ):
            _contract_at(self.loc.location_id)
            sells = _sell_at(self.loc.location_id)

        self.assertEqual(
            [row["item_name"] for row in sells["rows"]],
            ["Smoothed Baseline Ammo"],
        )
        gap = sells["rows"][0]
        self.assertEqual(gap["flags"], ["in_stock"])
        self.assertFalse(gap["coverage_gap"])
        self.assertFalse(gap["viability_gap"])
        self.assertFalse(
            any(r["coverage_gap"] or r["viability_gap"] for r in sells["rows"])
        )
        self.assertEqual(sells["summary"]["viability_pct"], 100.0)

    def test_overpriced_flags_on_viability_gap(self):
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
            "market.helpers.health_common.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            _contract_at(self.loc.location_id)
            sells = _sell_at(self.loc.location_id)

        gap = next(
            row
            for row in sells["rows"]
            if row["item_name"] == "Fat Overpriced Ammo"
        )
        self.assertFalse(gap["coverage_gap"])
        self.assertTrue(gap["viability_gap"])
        self.assertEqual(gap["avg_markup_pct"], 50.0)
        self.assertEqual(
            gap["flags"],
            ["in_stock", "overpriced"],
        )

    def test_understocked_contracts_returns_all_rows(self):
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

        contracts = _contract_at(self.loc.location_id)
        # setUp atron has outstanding stock → ready → omitted; 55 empty only.
        self.assertEqual(len(contracts["rows"]), 55)

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
            "market.helpers.health_common.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            _contract_at(self.loc.location_id)
            sells = _sell_at(self.loc.location_id)

        gap = next(
            row
            for row in sells["rows"]
            if row["item_name"] == "Viable Gap Ammo"
        )
        self.assertEqual(gap["current_quantity"], 100)
        self.assertEqual(gap["viable_quantity"], 11)
        # Presence desired=1; shortfall uses viable vs desired.
        self.assertEqual(gap["shortfall"], 0)
        self.assertFalse(gap["coverage_gap"])
        # Cheapest ask is within 20% of baseline → type is viable even
        # when most listed quantity sits above that.
        self.assertFalse(gap["viability_gap"])
        self.assertEqual(gap["item_type"], "consumable")
        self.assertEqual(sells["summary"]["targets"], 1)
        self.assertEqual(sells["summary"]["fulfilled"], 1)
        self.assertEqual(sells["summary"]["viable_fulfilled"], 1)
        self.assertEqual(sells["summary"]["health_pct"], 100.0)
        self.assertEqual(sells["summary"]["viability_pct"], 100.0)
        self.assertEqual(
            sum(
                1
                for r in sells["rows"]
                if r["coverage_gap"] or r["viability_gap"]
            ),
            0,
        )
        self.assertEqual(gap["flags"], ["in_stock", "overpriced"])
        self.assertIsNone(gap["days_of_stock"])

    def test_viability_uses_cheapest_ask_not_listed_mix(self):
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
            id=91024,
            defaults={
                "name": "Cheapest Ask Ammo",
                "published": True,
                "eve_group": charge_grp,
            },
        )
        EveMarketItemExpectation.objects.create(
            item=item,
            location=self.loc,
            quantity=100,
        )
        # Expensive majority first so aggregation cannot rely on insert order.
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=90,
            price=4_000_000,
            is_buy_order=False,
        )
        EveMarketItemOrder.objects.create(
            location=self.loc,
            item=item,
            quantity=1,
            price=2_000_000,
            is_buy_order=False,
        )

        with patch(
            "market.helpers.health_common.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            sells = _sell_at(self.loc.location_id)

        gap = next(
            row
            for row in sells["rows"]
            if row["item_name"] == "Cheapest Ask Ammo"
        )
        self.assertEqual(gap["viable_quantity"], 1)
        self.assertFalse(gap["viability_gap"])
        self.assertEqual(sells["summary"]["viability_pct"], 100.0)
        self.assertEqual(sells["summary"]["viable_fulfilled"], 1)

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
            "market.helpers.health_common.get_prices_by_type_id",
            return_value={item.pk: 2_000_000},
        ):
            _contract_at(self.loc.location_id)
            sells = _sell_at(self.loc.location_id)

        self.assertEqual(
            [row["item_name"] for row in sells["rows"]],
            ["Boundary Ammo"],
        )
        self.assertEqual(
            sells["rows"][0]["flags"],
            ["in_stock", "overpriced"],
        )
        self.assertFalse(
            any(r["coverage_gap"] or r["viability_gap"] for r in sells["rows"])
        )
        self.assertEqual(sells["summary"]["health_pct"], 100.0)
        self.assertEqual(sells["summary"]["viability_pct"], 100.0)
        self.assertEqual(sells["summary"]["viable_fulfilled"], 1)

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
            "market.helpers.health_common.get_prices_by_type_id",
            return_value={},
        ):
            _contract_at(self.loc.location_id)
            sells = _sell_at(self.loc.location_id)

        self.assertEqual(len(sells["rows"]), 1)
        self.assertEqual(sells["rows"][0]["item_name"], "No Baseline Ammo")
        self.assertEqual(sells["rows"][0]["flags"], ["in_stock"])
        self.assertFalse(
            any(r["coverage_gap"] or r["viability_gap"] for r in sells["rows"])
        )
        self.assertEqual(sells["summary"]["viability_pct"], 100.0)
        self.assertEqual(sells["summary"]["viable_fulfilled"], 1)

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
            "market.helpers.health_common.get_prices_by_type_id",
            return_value={item.pk: 50_000},
        ):
            _contract_at(self.loc.location_id)
            sells = _sell_at(self.loc.location_id)

        self.assertEqual(len(sells["rows"]), 1)
        self.assertEqual(sells["rows"][0]["item_name"], "Cheap Ammo")
        self.assertEqual(
            sells["rows"][0]["flags"],
            ["in_stock", "overpriced"],
        )
        self.assertFalse(sells["rows"][0]["coverage_gap"])
        self.assertFalse(sells["rows"][0]["viability_gap"])
        self.assertFalse(
            any(r["coverage_gap"] or r["viability_gap"] for r in sells["rows"])
        )
        self.assertEqual(sells["summary"]["viability_pct"], 100.0)
