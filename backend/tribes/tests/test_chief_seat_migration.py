"""Migration 0052 seats each group's single chief in their timezone."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

BEFORE = [
    ("tribes", "0051_move_fanfest_into_pulse"),
    ("timezones", "0001_initial"),
]
AFTER = [("tribes", "0052_tribe_group_chief_seats")]


class ChiefSeatMigrationTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(BEFORE)
        apps = executor.loader.project_state(BEFORE).apps
        user = apps.get_model("auth", "User")
        tribe = apps.get_model("tribes", "Tribe")
        group = apps.get_model("tribes", "TribeGroup")
        volunteer = apps.get_model("tribes", "TribeChiefVolunteer")
        pilot_timezone = apps.get_model("timezones", "PilotTimezone")
        now = timezone.now()

        self.eu = user.objects.create(username="eu-chief")
        self.unknown = user.objects.create(username="no-tz-chief")
        self.au_volunteer = user.objects.create(username="au-volunteer")
        self.us_volunteer = user.objects.create(username="us-volunteer")
        pilot_timezone.objects.create(
            user_id=self.eu.pk, home="EU", assessed_at=now, changed_at=now
        )
        pilot_timezone.objects.create(
            user_id=self.au_volunteer.pk,
            home=None,
            brackets=["AUTZ"],
            assessed_at=now,
            changed_at=now,
        )
        pilot_timezone.objects.create(
            user_id=self.us_volunteer.pk,
            home="US",
            assessed_at=now,
            changed_at=now,
        )
        t = tribe.objects.create(name="Mig", slug="mig-seats")
        self.eu_group = group.objects.create(
            tribe=t, name="A", code="mig.a", chief_id=self.eu.pk
        )
        self.unknown_group = group.objects.create(
            tribe=t, name="B", code="mig.b", chief_id=self.unknown.pk
        )
        self.empty_group = group.objects.create(
            tribe=t, name="C", code="mig.c"
        )
        self.au_offer = volunteer.objects.create(
            tribe=t, tribe_group=self.eu_group, user_id=self.au_volunteer.pk
        )
        # Their own seat (US) is taken in group B: they get the next free.
        self.moved_offer = volunteer.objects.create(
            tribe=t,
            tribe_group=self.unknown_group,
            user_id=self.us_volunteer.pk,
        )

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(AFTER)
        self.apps = executor.loader.project_state(AFTER).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_chiefs_take_their_timezone_seat(self):
        seat = self.apps.get_model("tribes", "TribeGroupChief")
        seats = {
            (row.tribe_group_id, row.region, row.user_id)
            for row in seat.objects.all()
        }
        self.assertEqual(
            seats,
            {
                (self.eu_group.pk, "EU", self.eu.pk),
                (self.unknown_group.pk, "US", self.unknown.pk),
            },
        )

    def test_pending_offers_get_a_free_seat(self):
        volunteer = self.apps.get_model("tribes", "TribeChiefVolunteer")
        self.assertEqual(
            volunteer.objects.get(pk=self.au_offer.pk).region, "AU"
        )
        self.assertEqual(
            volunteer.objects.get(pk=self.moved_offer.pk).region, "EU"
        )
