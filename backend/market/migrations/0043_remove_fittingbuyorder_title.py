"""Drop leftover FittingBuyOrder.title column.

An earlier local/prod schema for market.0042 included a required title
column. The model and 0042 were corrected to identify orders by ID only,
so Django state has no title — but MySQL still has the column and rejects
creates. Drop it at the database level when present.
"""

from django.db import migrations


def _drop_title_column(apps, schema_editor):
    table_name = "market_fittingbuyorder"
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(
            cursor, table_name
        )
    existing = {col.name for col in description}
    if "title" not in existing:
        return
    if connection.vendor == "mysql":
        schema_editor.execute(
            f"ALTER TABLE `{table_name}` DROP COLUMN `title`"
        )
    else:
        schema_editor.execute(
            f'ALTER TABLE "{table_name}" DROP COLUMN "title"'
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("market", "0042_fitting_buy_orders"),
    ]

    operations = [
        migrations.RunPython(_drop_title_column, migrations.RunPython.noop),
    ]
