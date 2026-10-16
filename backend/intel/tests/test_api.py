from datetime import timedelta
from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from eveonline.models import EveCharacter
from feed.models import FeedAmarrFleetAlert, FeedCapitalAlert
from intel.models import IntelReport
from intel.services import local as local_service
from intel.services.local import FRIENDLY, HOSTILE, NEUTRAL

from .test_paste import DSCAN_PASTE

AMAMAKE = 30002537


def auth_headers(user):
    token = jwt.encode(
        {"user_id": user.pk}, settings.SECRET_KEY, algorithm="HS256"
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def grant(user, *codenames):
    for codename in codenames:
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="intel", codename=codename
            )
        )


def fake_esi(ids=None, affiliations=None, names=None):
    """Patch the three bulk ESI lookups the Local resolver makes."""
    calls = []

    def _ids(chunk):
        calls.append(("ids", list(chunk)))
        return {n: i for n, i in (ids or {}).items() if n in chunk}

    def _aff(chunk):
        calls.append(("aff", list(chunk)))
        return {i: a for i, a in (affiliations or {}).items() if i in chunk}

    def _names(chunk):
        calls.append(("names", list(chunk)))
        return {i: n for i, n in (names or {}).items() if i in chunk}

    patches = [
        patch.object(local_service, "_esi_ids", side_effect=_ids),
        patch.object(local_service, "_esi_affiliations", side_effect=_aff),
        patch.object(local_service, "_esi_names", side_effect=_names),
    ]
    return patches, calls


class IntelApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create(username="scout")
        grant(self.user, "view_intelreport", "add_intelreport")
        EveCharacter.objects.create(
            character_id=1001, character_name="Ardo Kesh", user=self.user
        )
        self.headers = auth_headers(self.user)

    def post(self, path, body):
        return self.client.post(
            f"/api/intel{path}",
            body,
            content_type="application/json",
            **self.headers,
        )

    def test_share_dscan(self):
        response = self.post(
            "/reports",
            {
                "text": DSCAN_PASTE,
                "system": "amamake",
                "note": "  on the   Siseide gate ",
                "character_name": "ardo kesh",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["kind"], "dscan")
        self.assertEqual(data["system_id"], AMAMAKE)
        self.assertEqual(data["system_name"], "Amamake")
        self.assertEqual(data["reporter_name"], "Ardo Kesh")
        self.assertEqual(data["note"], "on the Siseide gate")
        self.assertEqual(data["summary"]["ships"], 5)
        self.assertEqual(data["summary_line"], "5 ships · 1 capsule · 2 other")

        detail = self.client.get(
            f"/api/intel/reports/{data['report_id']}", **self.headers
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["raw"], DSCAN_PASTE)

    def test_reporter_falls_back_when_character_is_not_yours(self):
        response = self.post(
            "/reports",
            {
                "text": DSCAN_PASTE,
                "system": "Amamake",
                "character_name": "Someone Else",
            },
        )
        self.assertEqual(response.json()["reporter_name"], "scout")

    def test_unknown_system_and_bad_paste(self):
        response = self.post(
            "/reports", {"text": DSCAN_PASTE, "system": "Nowhere"}
        )
        self.assertEqual(response.status_code, 400)
        response = self.post(
            "/reports", {"text": "not\tintel", "system": "Amamake"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(IntelReport.objects.count(), 0)

    def test_preview_saves_nothing_and_skips_esi(self):
        patches, calls = fake_esi()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        response = self.post(
            "/reports/preview", {"text": "Ardo Kesh\nNyra Holdt"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kind"], "local")
        self.assertEqual(response.json()["summary"]["pilots"], 2)
        self.assertEqual(calls, [])
        self.assertEqual(IntelReport.objects.count(), 0)

    def test_permissions(self):
        outsider = User.objects.create(username="outsider")
        headers = auth_headers(outsider)
        for method, path in [
            ("get", "/recent"),
            ("post", "/reports"),
            ("post", "/reports/preview"),
        ]:
            call = getattr(self.client, method)
            response = call(
                f"/api/intel{path}",
                *(
                    [{"text": DSCAN_PASTE, "system": "Amamake"}]
                    if method == "post"
                    else []
                ),
                content_type="application/json",
                **headers,
            )
            self.assertEqual(response.status_code, 403, path)
        self.assertEqual(self.client.get("/api/intel/recent").status_code, 401)

    def test_rate_limit(self):
        with patch("intel.router.REPORTS_PER_WINDOW", 2):
            codes = [
                self.post(
                    "/reports", {"text": DSCAN_PASTE, "system": "Amamake"}
                ).status_code
                for _ in range(3)
            ]
        self.assertEqual(codes, [200, 200, 429])

    def test_map_is_public_and_cacheable(self):
        response = self.client.get("/api/intel/map")
        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age", response["Cache-Control"])
        data = response.json()
        self.assertEqual(data["systems"][str(AMAMAKE)], "Amamake")
        self.assertTrue(data["edges"][str(AMAMAKE)])


class LocalReportTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create(username="scout")
        grant(self.user, "view_intelreport", "add_intelreport")
        self.headers = auth_headers(self.user)

    def share_local(self, names):
        return self.client.post(
            "/api/intel/reports",
            {"text": "\n".join(names), "system": "Siseide"},
            content_type="application/json",
            **self.headers,
        )

    def test_local_resolves_standings_and_caches(self):
        patches, calls = fake_esi(
            ids={"amarr one": 1, "amarr two": 2, "fleet pilot": 3, "rando": 4},
            affiliations={
                1: {
                    "corporation_id": 10,
                    "alliance_id": 500,
                    "faction_id": 500003,
                },
                2: {
                    "corporation_id": 11,
                    "alliance_id": 500,
                    "faction_id": None,
                },
                3: {
                    "corporation_id": 12,
                    "alliance_id": 99011978,
                    "faction_id": 500002,
                },
                4: {
                    "corporation_id": 13,
                    "alliance_id": None,
                    "faction_id": None,
                },
            },
            names={
                500: "Hostile Alliance",
                99011978: "Minmatar Fleet Alliance",
            },
        )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        names = ["Amarr One", "Amarr Two", "Fleet Pilot", "Rando", "Ghost"]
        data = self.share_local(names).json()
        summary = data["summary"]
        self.assertTrue(summary["resolved"])
        self.assertEqual(summary["pilots"], 5)
        self.assertEqual(summary["unknown"], 1)
        self.assertEqual(
            summary["standings"], {HOSTILE: 1, NEUTRAL: 2, FRIENDLY: 1}
        )
        self.assertEqual(
            summary["militia"], {"amarr": 1, "minmatar": 1, "none": 2}
        )
        alliances = {row["name"]: row for row in summary["alliances"]}
        self.assertEqual(alliances["Hostile Alliance"]["count"], 2)
        self.assertEqual(alliances["Hostile Alliance"]["standing"], HOSTILE)
        self.assertEqual(alliances["No alliance"]["count"], 1)

        # A second paste of the same pilots is served from the cache,
        # including the name ESI didn't know.
        calls.clear()
        second = self.share_local(names).json()
        self.assertEqual(calls, [])
        self.assertEqual(second["previous"]["hostile_delta"], 0)

    def test_esi_down_still_saves(self):
        with patch.object(local_service, "_esi_ids", return_value=None):
            data = self.share_local(["Amarr One", "Rando"]).json()
        self.assertFalse(data["summary"]["resolved"])
        self.assertEqual(data["summary_line"], "2 pilots")


class RecentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create(username="scout")
        grant(self.user, "view_intelreport", "add_intelreport")
        self.headers = auth_headers(self.user)

    def recent(self):
        response = self.client.get("/api/intel/recent", **self.headers)
        self.assertEqual(response.status_code, 200)
        return response.json()["items"]

    def test_merges_reports_and_pings_newest_first(self):
        now = timezone.now()
        FeedCapitalAlert.objects.create(
            solar_system_id=30003070,
            system_name="Sosala",
            distance_ly=6.1,
            capitals=[
                {
                    "type_id": 19720,
                    "name": "Revelation",
                    "role": "attacker",
                    "count": 1,
                },
                {
                    "type_id": 37604,
                    "name": "Apostle",
                    "role": "attacker",
                    "count": 2,
                },
            ],
            kills=[{"killmail_id": 1}, {"killmail_id": 2}],
            composition={"ship_counts": {"19720": 1, "37604": 2, "597": 5}},
            last_activity_at=now - timedelta(minutes=1),
        )
        FeedAmarrFleetAlert.objects.create(
            solar_system_id=30003072,
            system_name="Huola",
            systems=[
                {"solar_system_id": 30003069, "system_name": "Kamela"},
                {"solar_system_id": 30003072, "system_name": "Huola"},
            ],
            title="Amarr fleet",
            kills=4,
            pilots=22,
            ship_counts={"24696": 2, "2006": 6, "670": 3},
            cluster_key="fleet_active:x",
            last_activity_at=now - timedelta(minutes=12),
        )
        FeedAmarrFleetAlert.objects.create(
            solar_system_id=30003072,
            system_name="Old",
            title="Old fleet",
            cluster_key="fleet_active:old",
            last_activity_at=now - timedelta(hours=3),
        )
        self.client.post(
            "/api/intel/reports",
            {"text": DSCAN_PASTE, "system": "Amamake"},
            content_type="application/json",
            **self.headers,
        )

        items = self.recent()
        self.assertEqual(
            [item["kind"] for item in items], ["dscan", "caps", "fleet"]
        )
        dscan, caps, fleet = items
        self.assertFalse(dscan["is_ping"])
        self.assertEqual(dscan["image"], {"kind": "type", "id": 597})
        self.assertEqual(dscan["ships"][0]["name"], "Zealot")
        self.assertEqual(
            caps["summary"],
            "Revelation + 2 Apostle · 6.1 ly from Amamake · 2 kills",
        )
        self.assertEqual(
            [s["name"] for s in caps["ships"]],
            ["Revelation", "Apostle", "Punisher"],
        )
        self.assertEqual(
            fleet["summary"],
            "Amarr fleet · ~22 pilots · 4 kills · moved from Kamela",
        )
        self.assertEqual(
            [(s["name"], s["count"]) for s in fleet["ships"]],
            [("Harbinger", 2), ("Omen", 6)],
        )

    def test_cached_until_a_report_is_shared(self):
        self.assertEqual(self.recent(), [])
        FeedAmarrFleetAlert.objects.create(
            solar_system_id=30003072,
            system_name="Huola",
            title="Amarr fleet",
            cluster_key="fleet_active:y",
            last_activity_at=timezone.now(),
        )
        self.assertEqual(self.recent(), [])  # still the cached list
        self.client.post(
            "/api/intel/reports",
            {"text": DSCAN_PASTE, "system": "Amamake"},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(len(self.recent()), 2)
