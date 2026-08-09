# Replace EveMarketOpsMonitorSnapshot with a single kind-scoped health table.

import json

import django.db.models.deletion
from django.core.serializers.json import DjangoJSONEncoder
from django.db import migrations, models


def copy_ops_monitor_snapshots(apps, schema_editor):
    Old = apps.get_model("market", "EveMarketOpsMonitorSnapshot")
    Health = apps.get_model("market", "EveMarketHealthSnapshot")

    old_count = Old.objects.count()
    if old_count == 0:
        return

    existing = Health.objects.count()
    if existing:
        if existing == old_count * 2:
            return
        raise RuntimeError(
            "market 0038: health snapshot table is partially populated "
            f"(health={existing}, old={old_count}). "
            "Resolve manually before re-running."
        )

    connection = schema_editor.connection
    table = Health._meta.db_table
    qn = connection.ops.quote_name
    cols = [
        "captured_at",
        "kind",
        "location_id",
        "health_pct",
        "viability_pct",
        "targets",
        "fulfilled",
        "viable_fulfilled",
        "isk",
        "synced_at",
        "history_days",
    ]
    col_sql = ", ".join(qn(c) for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO {qn(table)} ({col_sql}) VALUES ({placeholders})"

    batch = []
    source_pairs = []

    def _flush():
        nonlocal batch
        if not batch:
            return
        with connection.cursor() as cursor:
            cursor.executemany(insert_sql, batch)
        batch = []

    for snap in Old.objects.order_by("id").iterator(chunk_size=500):
        source_pairs.append((snap.location_id, snap.captured_at))
        batch.append(
            [
                snap.captured_at,
                "contracts",
                snap.location_id,
                snap.contracts_health_pct,
                getattr(snap, "contracts_viability_pct", None),
                snap.contract_targets,
                snap.contract_fulfilled,
                getattr(snap, "contract_viable_fulfilled", 0) or 0,
                snap.contracts_isk,
                snap.contracts_synced_at,
                0,
            ]
        )
        batch.append(
            [
                snap.captured_at,
                "sell_orders",
                snap.location_id,
                snap.sell_orders_health_pct,
                snap.sell_orders_viability_pct,
                snap.sell_order_targets,
                snap.sell_order_fulfilled,
                snap.sell_order_viable_fulfilled,
                snap.sell_orders_isk,
                snap.orders_synced_at,
                0,
            ]
        )
        if len(batch) >= 1000:
            _flush()

    _flush()

    health_count = Health.objects.count()
    if health_count != old_count * 2:
        raise RuntimeError(
            "market 0038: snapshot copy count mismatch "
            f"(old={old_count}, health={health_count}, expected={old_count * 2})."
        )

    contract_keys = {
        (row.location_id, row.captured_at)
        for row in Health.objects.filter(kind="contracts").only(
            "location_id", "captured_at"
        )
    }
    sell_keys = {
        (row.location_id, row.captured_at)
        for row in Health.objects.filter(kind="sell_orders").only(
            "location_id", "captured_at"
        )
    }
    missing_contract = [
        key for key in source_pairs if key not in contract_keys
    ]
    missing_sell = [key for key in source_pairs if key not in sell_keys]
    if missing_contract or missing_sell:
        raise RuntimeError(
            "market 0038: captured_at not preserved after copy "
            f"(missing_contract={len(missing_contract)}, "
            f"missing_sell={len(missing_sell)})."
        )


def _combined_health(contracts_pct, sell_orders_pct):
    parts = [p for p in (contracts_pct, sell_orders_pct) if p is not None]
    if not parts:
        return None
    return round(sum(parts) / len(parts), 1)


def reverse_ops_monitor_snapshots(apps, schema_editor):
    Old = apps.get_model("market", "EveMarketOpsMonitorSnapshot")
    Health = apps.get_model("market", "EveMarketHealthSnapshot")

    connection = schema_editor.connection
    qn = connection.ops.quote_name
    table = Old._meta.db_table
    cols = [
        "captured_at",
        "location_id",
        "trigger",
        "contracts_health_pct",
        "contracts_viability_pct",
        "sell_orders_health_pct",
        "sell_orders_viability_pct",
        "overall_health_pct",
        "understocked_contracts_count",
        "sell_gaps_count",
        "contract_targets",
        "contract_fulfilled",
        "contract_viable_fulfilled",
        "sell_order_targets",
        "sell_order_fulfilled",
        "sell_order_viable_fulfilled",
        "contracts_isk",
        "sell_orders_isk",
        "total_isk_on_market",
        "contracts_synced_at",
        "orders_synced_at",
        "understocked_contracts",
        "sell_gaps",
    ]
    col_sql = ", ".join(qn(c) for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO {qn(table)} ({col_sql}) VALUES ({placeholders})"

    sell_by_key = {
        (row.location_id, row.captured_at): row
        for row in Health.objects.filter(kind="sell_orders")
    }
    batch = []
    for crow in (
        Health.objects.filter(kind="contracts")
        .order_by("id")
        .iterator(chunk_size=500)
    ):
        srow = sell_by_key.get((crow.location_id, crow.captured_at))
        if srow is None:
            continue
        understocked = json.dumps([], cls=DjangoJSONEncoder)
        sell_gaps = json.dumps([], cls=DjangoJSONEncoder)
        batch.append(
            [
                crow.captured_at,
                crow.location_id,
                "contracts",
                crow.health_pct,
                crow.viability_pct,
                srow.health_pct,
                srow.viability_pct,
                _combined_health(crow.health_pct, srow.health_pct),
                0,
                0,
                crow.targets,
                crow.fulfilled,
                crow.viable_fulfilled,
                srow.targets,
                srow.fulfilled,
                srow.viable_fulfilled,
                crow.isk,
                srow.isk,
                float(crow.isk or 0) + float(srow.isk or 0),
                crow.synced_at,
                srow.synced_at,
                understocked,
                sell_gaps,
            ]
        )
        if len(batch) >= 500:
            with connection.cursor() as cursor:
                cursor.executemany(insert_sql, batch)
            batch = []
    if batch:
        with connection.cursor() as cursor:
            cursor.executemany(insert_sql, batch)


def drop_leftover_legacy_table(apps, schema_editor):
    from django.db import connection

    legacy = "market_evemarketopsmonitorsnapshot"
    if legacy not in connection.introspection.table_names():
        return

    Health = apps.get_model("market", "EveMarketHealthSnapshot")
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {connection.ops.quote_name(legacy)}"
        )
        legacy_count = cursor.fetchone()[0]

    if legacy_count == 0 or Health.objects.exists():
        with connection.cursor() as cursor:
            cursor.execute(
                f"DROP TABLE IF EXISTS {connection.ops.quote_name(legacy)}"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0101_evecorporation_trial"),
        ("market", "0037_market_contract_issuer_corporation"),
    ]

    operations = [
        migrations.CreateModel(
            name="EveMarketHealthSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "captured_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("contracts", "Contracts"),
                            ("sell_orders", "Sell orders"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("health_pct", models.FloatField(blank=True, null=True)),
                ("viability_pct", models.FloatField(blank=True, null=True)),
                ("targets", models.PositiveIntegerField(default=0)),
                ("fulfilled", models.PositiveIntegerField(default=0)),
                ("viable_fulfilled", models.PositiveIntegerField(default=0)),
                ("isk", models.FloatField(default=0.0)),
                ("synced_at", models.DateTimeField(blank=True, null=True)),
                ("history_days", models.PositiveIntegerField(default=0)),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="health_snapshots",
                        to="eveonline.evelocation",
                    ),
                ),
            ],
            options={
                "verbose_name": "EVE market health snapshot",
                "verbose_name_plural": "EVE market health snapshots",
                "ordering": ["-captured_at"],
            },
        ),
        migrations.AddIndex(
            model_name="evemarkethealthsnapshot",
            index=models.Index(
                fields=["kind", "location", "-captured_at"],
                name="market_hlth_kind_loc_captured",
            ),
        ),
        migrations.RunPython(
            copy_ops_monitor_snapshots,
            reverse_ops_monitor_snapshots,
        ),
        migrations.DeleteModel(
            name="EveMarketOpsMonitorSnapshot",
        ),
        migrations.RunPython(
            drop_leftover_legacy_table,
            migrations.RunPython.noop,
        ),
    ]
