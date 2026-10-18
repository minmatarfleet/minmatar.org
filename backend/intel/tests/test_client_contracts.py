"""Intel payloads installed desktop versions render (app/contracts.py).

The desktop's Intel window reads the recent sheet (/api/intel/recent) and
opens one report (/api/intel/reports/{id}). A made-up d-scan and a capital
ping cover both item kinds.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from app import contracts
from eveonline.models import EveCharacter
from feed.models import FeedCapitalAlert
from intel.models import IntelReport

from .test_api import auth_headers, grant
from .test_paste import DSCAN_PASTE

REPORT_ID = "contract1"


class IntelContractTests(TestCase):
    def setUp(self):
        cache.clear()
        clock = contracts.frozen_clock()
        clock.start()
        self.addCleanup(clock.stop)
        self.user = User.objects.create(id=7101, username="scout")
        grant(self.user, "view_intelreport", "add_intelreport")
        EveCharacter.objects.create(
            character_id=1001, character_name="Ardo Kesh", user=self.user
        )
        self.headers = auth_headers(self.user)
        response = self.client.post(
            "/api/intel/reports",
            {
                "text": DSCAN_PASTE,
                "system": "Amamake",
                "note": "on the Siseide gate",
                "character_name": "Ardo Kesh",
            },
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 200, response.content)
        # Shared links are random; pin this one so the file is stable.
        IntelReport.objects.update(public_id=REPORT_ID)
        FeedCapitalAlert.objects.create(
            id=1,
            solar_system_id=30003070,
            system_name="Sosala",
            distance_ly=6.1,
            capitals=[
                {
                    "type_id": 19720,
                    "name": "Revelation",
                    "role": "attacker",
                    "count": 1,
                }
            ],
            kills=[{"killmail_id": 1}],
            composition={"ship_counts": {"19720": 1, "597": 5}},
            last_activity_at=contracts.FIXED_NOW - timedelta(minutes=3),
        )
        cache.clear()

    def _get(self, path):
        response = self.client.get(f"/api/intel{path}", **self.headers)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_intel_recent(self):
        contracts.check(
            self, contracts.DESKTOP / "intel_recent.json", self._get("/recent")
        )

    def test_intel_report(self):
        contracts.check(
            self,
            contracts.DESKTOP / "intel_report.json",
            self._get(f"/reports/{REPORT_ID}"),
        )
