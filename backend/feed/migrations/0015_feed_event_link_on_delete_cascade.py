# Production MySQL FKs on feed event links are RESTRICT despite CASCADE on the
# Django models, so AlterField is a no-op. Recreate them with ON DELETE CASCADE.

from django.db import migrations

_TABLES = (
    "feed_feedeventkillmaillink",
    "feed_feedeventfleetlink",
)


def _alter_feed_event_fks_to_cascade(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return

    with schema_editor.connection.cursor() as cursor:
        for table in _TABLES:
            cursor.execute(
                """
                SELECT CONSTRAINT_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = 'feed_event_id'
                  AND REFERENCED_TABLE_NAME = 'feed_feedevent'
                """,
                [table],
            )
            names = [row[0] for row in cursor.fetchall()]
            for name in names:
                if not str(name).replace("_", "").isalnum():
                    raise ValueError(f"unexpected FK name {name!r}")
                cursor.execute(
                    f"ALTER TABLE `{table}` DROP FOREIGN KEY `{name}`"
                )
            cursor.execute(f"""
                ALTER TABLE `{table}`
                ADD CONSTRAINT `{table}_feed_event_id_fk`
                FOREIGN KEY (`feed_event_id`)
                REFERENCES `feed_feedevent` (`id`)
                ON DELETE CASCADE
                """)


def _alter_feed_event_fks_to_restrict(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return

    with schema_editor.connection.cursor() as cursor:
        for table in _TABLES:
            cursor.execute(
                """
                SELECT CONSTRAINT_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = 'feed_event_id'
                  AND REFERENCED_TABLE_NAME = 'feed_feedevent'
                """,
                [table],
            )
            names = [row[0] for row in cursor.fetchall()]
            for name in names:
                if not str(name).replace("_", "").isalnum():
                    raise ValueError(f"unexpected FK name {name!r}")
                cursor.execute(
                    f"ALTER TABLE `{table}` DROP FOREIGN KEY `{name}`"
                )
            cursor.execute(f"""
                ALTER TABLE `{table}`
                ADD CONSTRAINT `{table}_feed_event_id_fk`
                FOREIGN KEY (`feed_event_id`)
                REFERENCES `feed_feedevent` (`id`)
                """)


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0014_remove_stale_celery_beat_tasks"),
    ]

    operations = [
        migrations.RunPython(
            _alter_feed_event_fks_to_cascade,
            _alter_feed_event_fks_to_restrict,
        ),
    ]
