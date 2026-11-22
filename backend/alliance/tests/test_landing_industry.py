"""The homepage week table's Industry tab: finished jobs only."""

from datetime import timedelta
from itertools import count

from django.core.cache import cache
from django.utils import timezone
from eveuniverse.models import (
    EveCategory,
    EveGroup,
    EveIndustryActivityProduct,
    EveMarketPrice,
    EveType,
)

from alliance.helpers.landing_week import build_week, landing_week
from app.test import TestCase
from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.models import EveCharacter, EveCharacterIndustryJob

JOB_IDS = count(1)


class LandingIndustryTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.now = timezone.now()
        self.pilot = EveCharacter.objects.create(
            character_id=2001,
            character_name="Orion Sa-Solo",
            alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
        )
        ships = EveGroup.objects.create(
            id=25,
            name="Frigate",
            published=True,
            eve_category=EveCategory.objects.create(
                id=6, name="Ship", published=True
            ),
        )
        blueprints = EveGroup.objects.create(
            id=105,
            name="Frigate Blueprint",
            published=True,
            eve_category=EveCategory.objects.create(
                id=9, name="Blueprint", published=True
            ),
        )
        self.rifter = EveType.objects.create(
            id=587, name="Rifter", published=True, eve_group=ships
        )
        self.rifter_bp = EveType.objects.create(
            id=691,
            name="Rifter Blueprint",
            published=True,
            eve_group=blueprints,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=self.rifter_bp,
            activity_id=1,
            product_eve_type=self.rifter,
            quantity=1,
        )
        EveMarketPrice.objects.create(
            eve_type=self.rifter, average_price=500_000.0
        )

    def _job(self, activity_id, ended_ago, runs=1, status="delivered"):
        end = self.now - ended_ago
        return EveCharacterIndustryJob.objects.create(
            job_id=next(JOB_IDS),
            character=self.pilot,
            activity_id=activity_id,
            blueprint_id=1,
            blueprint_type_id=self.rifter_bp.id,
            blueprint_location_id=1,
            facility_id=1,
            location_id=1,
            output_location_id=1,
            status=status,
            installer_id=self.pilot.character_id,
            start_date=end - timedelta(hours=1),
            end_date=end,
            duration=3600,
            runs=runs,
        )

    def _rows(self):
        return build_week(self.now)["tabs"]["industry"]

    def test_a_finished_build_names_the_product_and_its_value(self):
        self._job(1, timedelta(hours=2), runs=10)
        [row] = self._rows()
        self.assertEqual(row["action"], "built 10 × Rifter")
        self.assertEqual(row["subject_id"], self.rifter.id)
        self.assertEqual(row["amount"], 5_000_000)
        self.assertEqual(row["occurred_at"], self.now - timedelta(hours=2))

    def test_running_and_cancelled_jobs_never_show(self):
        # Still running: ends in an hour. Its start must not leak.
        self._job(1, -timedelta(hours=1), status="active")
        self._job(1, timedelta(hours=3), status="cancelled")
        self.assertEqual(self._rows(), [])

    def test_finished_but_not_delivered_shows(self):
        self._job(1, timedelta(minutes=30), status="active")
        self.assertEqual(len(self._rows()), 1)

    def test_a_batch_finishing_together_is_one_line(self):
        first = self._job(1, timedelta(hours=1), runs=5)
        second = self._job(1, timedelta(hours=1), runs=7)
        EveCharacterIndustryJob.objects.filter(pk=second.pk).update(
            end_date=first.end_date
        )
        self._job(1, timedelta(hours=5), runs=1)
        self.assertEqual(
            [row["action"] for row in self._rows()],
            ["built 12 × Rifter", "built 1 × Rifter"],
        )

    def test_research_copies_and_invention_name_the_blueprint(self):
        self._job(4, timedelta(hours=1))
        self._job(5, timedelta(hours=2), runs=10)
        self._job(8, timedelta(hours=3), runs=1)
        rows = self._rows()
        self.assertEqual(
            [row["action"] for row in rows],
            [
                "researched Rifter Blueprint",
                "made 10 copies of Rifter Blueprint",
                "finished 1 invention run on Rifter Blueprint",
            ],
        )
        # The icon is the product's; research has no value column.
        self.assertEqual({row["subject_id"] for row in rows}, {self.rifter.id})
        self.assertEqual({row["amount"] for row in rows}, {0})

    def test_older_than_a_week_is_left_out(self):
        self._job(1, timedelta(days=8))
        self.assertEqual(self._rows(), [])

    def test_counted_in_the_week_response(self):
        self._job(1, timedelta(hours=1))
        week = landing_week("industry", 1)
        self.assertEqual(week["tab"], "industry")
        self.assertEqual(week["counts"]["industry"], 1)

    def test_endpoint_serves_the_tab(self):
        self._job(1, timedelta(hours=1))
        response = self.client.get("/api/alliance/landing/week?tab=industry")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["counts"]["industry"], 1)
        self.assertEqual(data["rows"][0]["kind"], "industry")
