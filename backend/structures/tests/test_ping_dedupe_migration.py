"""0025 removes duplicate structure pings before notification_id turns unique."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, tag


@tag("migration")
class StructurePingDedupeMigrationTest(TransactionTestCase):
    def test_keeps_the_posted_row_or_the_oldest(self):
        executor = MigrationExecutor(connection)
        migrate_from = [("structures", "0024_locations_public_by_default")]
        migrate_to = [
            ("structures", "0025_unique_structure_ping_notification")
        ]

        executor.migrate(migrate_from)
        ping = executor.loader.project_state(migrate_from).apps.get_model(
            "structures", "EveStructurePing"
        )

        def make(notification_id, posted=False):
            return ping.objects.create(
                notification_id=notification_id,
                notification_type="StructureLostArmor",
                summary="",
                discord_success=posted,
            )

        oldest = make(1)
        make(1)
        make(2)
        posted = make(2, posted=True)
        single = make(3)

        executor.loader.build_graph()
        executor.migrate(migrate_to)

        after = executor.loader.project_state(migrate_to).apps.get_model(
            "structures", "EveStructurePing"
        )
        self.assertEqual(
            [oldest.id, posted.id, single.id],
            list(after.objects.order_by("id").values_list("id", flat=True)),
        )
