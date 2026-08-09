"""Data-migration integrity for ops monitor → kind-scoped health snapshots."""

from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class MarketHealthSnapshotMigrationTestCase(TransactionTestCase):
    """
    Apply 0037 → seed legacy rows → apply 0038 → assert copy + drop.
    """

    def test_0038_copies_all_rows_preserves_captured_at_and_drops_legacy(self):
        executor = MigrationExecutor(connection)
        app = "market"
        migrate_from = [(app, "0037_market_contract_issuer_corporation")]
        migrate_to = [(app, "0038_market_health_snapshots")]

        executor.migrate(migrate_from)
        old_state = executor.loader.project_state(migrate_from)
        old_snapshot = old_state.apps.get_model(
            "market", "EveMarketOpsMonitorSnapshot"
        )
        location_model = old_state.apps.get_model("eveonline", "EveLocation")

        loc = location_model.objects.create(
            location_id=4242,
            location_name="Migration Test",
            short_name="MigTest",
            solar_system_id=1,
            solar_system_name="Jita",
            market_active=True,
        )
        t0 = timezone.now() - timedelta(days=3)
        t1 = timezone.now() - timedelta(hours=5)
        first = old_snapshot.objects.create(
            location_id=loc.pk,
            trigger="contracts",
            contracts_health_pct=80.0,
            contracts_viability_pct=70.0,
            sell_orders_health_pct=60.0,
            sell_orders_viability_pct=55.0,
            overall_health_pct=70.0,
            understocked_contracts_count=2,
            sell_gaps_count=3,
            contract_targets=4,
            contract_fulfilled=3,
            contract_viable_fulfilled=2,
            sell_order_targets=5,
            sell_order_fulfilled=4,
            sell_order_viable_fulfilled=3,
            contracts_isk=100.0,
            sell_orders_isk=200.0,
            total_isk_on_market=300.0,
            understocked_contracts=[{"fitting_name": "A"}],
            sell_gaps=[{"item_name": "B", "coverage_gap": True}],
        )
        old_snapshot.objects.filter(pk=first.pk).update(captured_at=t0)
        second = old_snapshot.objects.create(
            location_id=loc.pk,
            trigger="orders",
            contracts_health_pct=90.0,
            sell_orders_health_pct=40.0,
            sell_orders_viability_pct=35.0,
            understocked_contracts_count=0,
            sell_gaps_count=1,
            understocked_contracts=[],
            sell_gaps=[{"item_name": "C", "viability_gap": True}],
        )
        old_snapshot.objects.filter(pk=second.pk).update(captured_at=t1)
        self.assertEqual(old_snapshot.objects.count(), 2)

        executor.loader.build_graph()
        executor.migrate(migrate_to)

        new_state = executor.loader.project_state(migrate_to)
        health_snapshot = new_state.apps.get_model(
            "market", "EveMarketHealthSnapshot"
        )

        self.assertEqual(health_snapshot.objects.count(), 4)
        contracts = {
            row.captured_at: row
            for row in health_snapshot.objects.filter(kind="contracts")
        }
        sells = {
            row.captured_at: row
            for row in health_snapshot.objects.filter(kind="sell_orders")
        }
        self.assertEqual(contracts[t0].health_pct, 80.0)
        self.assertEqual(contracts[t0].targets, 4)
        self.assertEqual(contracts[t1].health_pct, 90.0)
        self.assertEqual(sells[t0].targets, 5)
        self.assertEqual(sells[t1].health_pct, 40.0)

        tables = connection.introspection.table_names()
        self.assertNotIn("market_evemarketopsmonitorsnapshot", tables)
