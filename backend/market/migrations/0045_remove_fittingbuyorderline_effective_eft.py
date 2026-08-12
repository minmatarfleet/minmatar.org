"""Drop leftover FittingBuyOrderLine.effective_eft column.

An earlier local/prod schema for market.0042 included a required
effective_eft column. The model and 0042 now compute EFT at read time,
so Django state has no effective_eft — but MySQL still has the column and
rejects creates with IntegrityError 1364. Drop it when present.
"""

from django.db import migrations


def _drop_effective_eft_column(apps, schema_editor):
    table_name = "market_fittingbuyorderline"
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(
            cursor, table_name
        )
    existing = {col.name for col in description}
    if "effective_eft" not in existing:
        return
    if connection.vendor == "mysql":
        schema_editor.execute(
            f"ALTER TABLE `{table_name}` DROP COLUMN `effective_eft`"
        )
    else:
        schema_editor.execute(
            f'ALTER TABLE "{table_name}" DROP COLUMN "effective_eft"'
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("market", "0044_fitting_buy_pending_fitting"),
    ]

    operations = [
        migrations.RunPython(
            _drop_effective_eft_column, migrations.RunPython.noop
        ),
    ]
