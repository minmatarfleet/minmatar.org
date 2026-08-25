# Drop leftover Mumble credential table after the mumble app was hard-deleted.

from django.db import migrations

LEGACY_TABLES = ("mumble_mumbleaccess",)


def drop_legacy_mumble_tables(apps, schema_editor):
    connection = schema_editor.connection
    existing = set(connection.introspection.table_names())
    with connection.cursor() as cursor:
        for table in LEGACY_TABLES:
            if table in existing:
                cursor.execute(
                    f"DROP TABLE IF EXISTS {connection.ops.quote_name(table)}"
                )


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0026_remove_mumble_feature_and_tasks"),
    ]

    operations = [
        migrations.RunPython(
            drop_legacy_mumble_tables,
            migrations.RunPython.noop,
        ),
    ]
