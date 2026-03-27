from django.db import migrations


def _drop_legacy_columns(apps, schema_editor):
    table_name = "srp_shipreimbursementprogram"
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(
            cursor, table_name
        )
    existing = {col.name for col in description}

    for col in ("kind", "name", "program_key"):
        if col not in existing:
            continue
        if connection.vendor == "mysql":
            schema_editor.execute(
                f"ALTER TABLE `{table_name}` DROP COLUMN `{col}`"
            )
        else:
            schema_editor.execute(
                f'ALTER TABLE "{table_name}" DROP COLUMN "{col}"'
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("srp", "0019_merge_20260327_1305"),
    ]

    operations = [
        migrations.RunPython(_drop_legacy_columns, migrations.RunPython.noop),
    ]
