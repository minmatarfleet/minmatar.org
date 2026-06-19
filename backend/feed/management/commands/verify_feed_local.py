from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.core.management.base import BaseCommand
from django.test import Client

from feed.helpers.clusters import detect_clusters
from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.helpers.zkill_fetch import fetch_killmail_r2z2_payload
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import (
    FeedCluster,
    FeedEvent,
    FeedEventAnnouncementLink,
    FeedEventFleetLink,
    FeedEventKillmailLink,
    FeedKillmail,
    FeedMilitiaFirstSeen,
    FeedMonitoredSystem,
)
from feed.tasks import run_feed_rollups
from feed.tests.helpers import make_killmail_payload

# From verification_cases_research.md
GOLDEN_SIBLINGS = [
    136398967,
    136398973,
    136398981,
    136398992,
    136398976,
    136398970,
    136398640,
    136399100,
    136398972,
    136398988,
    136398996,
    136399016,
    136399113,
]

NEGATIVE_CASES = {
    "N1_jita": 136400936,
    "N2_npc": 136386594,
    "N3_solo": 136400805,
    "N4_tama": 136400880,
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


class Command(BaseCommand):
    help = (
        "Live local verification against research cases: "
        "fetch real zKill/ESI killmails, run ingest→clusters→rollups, assert outcomes"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-network",
            action="store_true",
            help="Use fixture anchor + synthetic padding only (no zKill/ESI)",
        )
        parser.add_argument(
            "--golden-only",
            action="store_true",
            help="Skip negative control fetches",
        )

    def handle(self, *args, **options):
        results: list[CheckResult] = []
        self._reset_feed_data()
        seed_from_fixture()

        huola = FeedMonitoredSystem.objects.filter(name="Huola").first()
        results.append(
            CheckResult(
                "Fixture Huola ID",
                huola is not None and huola.solar_system_id == 30003067,
                f"Huola solar_system_id={getattr(huola, 'solar_system_id', None)}",
            )
        )

        if options["skip_network"]:
            self._ingest_fixture_anchor()
        else:
            self._ingest_live_golden()
            if not options["golden_only"]:
                self._ingest_negative_controls(results)

        kill_count = FeedKillmail.objects.count()
        results.append(
            CheckResult(
                "Golden ingest count",
                kill_count >= 5,
                f"{kill_count} FeedKillmail rows",
            )
        )

        detect_clusters(since_hours=72)
        run_feed_rollups(since_hours=72)

        if not options["skip_network"] and not options["golden_only"]:
            results.extend(self._assert_solo_not_clustered())

        results.extend(self._assert_golden_cluster())
        results.extend(self._assert_events())
        results.extend(self._assert_api())
        results.extend(self._assert_scope())

        self.stdout.write("\n=== Feed local verification ===\n")
        passed = 0
        for check in results:
            status = (
                self.style.SUCCESS("PASS")
                if check.passed
                else self.style.ERROR("FAIL")
            )
            self.stdout.write(f"  [{status}] {check.name}: {check.detail}")
            if check.passed:
                passed += 1

        self.stdout.write(f"\n{passed}/{len(results)} checks passed\n")
        if passed < len(results):
            raise SystemExit(1)

    def _reset_feed_data(self) -> None:
        FeedEventKillmailLink.objects.all().delete()
        FeedEventAnnouncementLink.objects.all().delete()
        FeedEventFleetLink.objects.all().delete()
        FeedEvent.objects.all().delete()
        FeedCluster.objects.all().delete()
        FeedKillmail.objects.all().delete()
        FeedMilitiaFirstSeen.objects.all().delete()

    def _ingest_fixture_anchor(self) -> None:
        path = (
            Path(__file__).resolve().parent.parent.parent
            / "tests"
            / "fixtures"
            / "engagement_vard_136398967"
            / "killmail_136398967.json"
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        upsert_feed_killmail_from_r2z2(payload)

        anchor = datetime(2026, 6, 19, 17, 25, 8, tzinfo=timezone.utc)
        for i, kid in enumerate(
            [136398973, 136398981, 136398992, 136398976, 136398970]
        ):
            upsert_feed_killmail_from_r2z2(
                make_killmail_payload(
                    kid,
                    killmail_time=anchor
                    - timedelta(minutes=8)
                    + timedelta(minutes=i * 2),
                    attacker_count=8,
                )
            )

    def _ingest_live_golden(self) -> None:
        self.stdout.write(
            "Fetching golden engagement killmails from zKill/ESI..."
        )
        imported = 0
        for killmail_id in GOLDEN_SIBLINGS:
            payload = fetch_killmail_r2z2_payload(killmail_id)
            if payload is None:
                self.stderr.write(f"  skip {killmail_id} (fetch failed)")
                continue
            if upsert_feed_killmail_from_r2z2(payload):
                imported += 1
                self.stdout.write(f"  imported {killmail_id}")
        self.stdout.write(
            f"Golden engagement: {imported}/{len(GOLDEN_SIBLINGS)} imported"
        )

    def _ingest_negative_controls(self, results: list[CheckResult]) -> None:
        self.stdout.write("Fetching negative control killmails...")
        for label, killmail_id in NEGATIVE_CASES.items():
            payload = fetch_killmail_r2z2_payload(killmail_id)
            if payload is None:
                results.append(
                    CheckResult(
                        f"{label} fetch",
                        False,
                        f"could not fetch {killmail_id}",
                    )
                )
                continue
            before = FeedKillmail.objects.filter(
                killmail_id=killmail_id
            ).count()
            upsert_feed_killmail_from_r2z2(payload)
            after = FeedKillmail.objects.filter(
                killmail_id=killmail_id
            ).count()
            if label == "N3_solo":
                results.append(
                    CheckResult(
                        f"{label} ingested",
                        after == 1,
                        f"rows={after} (cluster check after rollups)",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        f"{label} discarded",
                        after == 0 and before == 0,
                        f"killmail_id={killmail_id} rows={after}",
                    )
                )

    def _assert_solo_not_clustered(self) -> list[CheckResult]:
        solo_id = NEGATIVE_CASES["N3_solo"]
        solo_only = any(
            (c.killmail_ids or []) == [solo_id]
            for c in FeedCluster.objects.all()
        )
        return [
            CheckResult(
                "N3_solo no solo cluster",
                not solo_only,
                f"solo_only_cluster={solo_only}",
            )
        ]

    def _assert_golden_cluster(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        fleet = FeedCluster.objects.filter(
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002538,
        )
        anchor_fleet = None
        for c in fleet:
            if 136398967 in (c.killmail_ids or []):
                anchor_fleet = c
                break
        if anchor_fleet:
            results.append(
                CheckResult(
                    "P1 fleet cluster (anchor)",
                    anchor_fleet.kill_count >= 5
                    and anchor_fleet.pilot_count >= 8,
                    f"kills={anchor_fleet.kill_count} pilots={anchor_fleet.pilot_count}",
                )
            )
        else:
            results.append(
                CheckResult(
                    "P1 fleet cluster (anchor)",
                    False,
                    "no fleet cluster contains anchor",
                )
            )

        burst = FeedCluster.objects.filter(
            cluster_type=FeedCluster.ClusterType.KILL_BURST,
            solar_system_id=30002538,
        ).first()
        if burst:
            results.append(
                CheckResult(
                    "P1 kill burst cluster",
                    burst.kill_count >= 8,
                    f"kills={burst.kill_count}",
                )
            )
        else:
            results.append(
                CheckResult(
                    "P1 kill burst cluster", False, "no kill_burst cluster"
                )
            )
        return results

    def _assert_events(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        fleet_event = None
        for event in FeedEvent.objects.filter(
            kind=FeedEvent.Kind.FLEET_ACTIVE
        ):
            if FeedKillmail.objects.filter(killmail_id=136398967).exists():
                anchor = FeedKillmail.objects.get(killmail_id=136398967)
                if FeedEventKillmailLink.objects.filter(
                    feed_event=event, feed_killmail=anchor
                ).exists():
                    fleet_event = event
                    break
        if fleet_event is None:
            fleet_event = FeedEvent.objects.filter(
                kind=FeedEvent.Kind.FLEET_ACTIVE
            ).first()
        if fleet_event:
            anchor_linked = False
            if FeedKillmail.objects.filter(killmail_id=136398967).exists():
                anchor = FeedKillmail.objects.get(killmail_id=136398967)
                anchor_linked = FeedEventKillmailLink.objects.filter(
                    feed_event=fleet_event, feed_killmail=anchor
                ).exists()
            results.append(
                CheckResult(
                    "P1 fleet_active event",
                    fleet_event.payload.get("faction") == "minmatar"
                    and anchor_linked,
                    f"title={fleet_event.title!r} accent={fleet_event.accent} "
                    f"anchor_linked={anchor_linked}",
                )
            )
        else:
            results.append(
                CheckResult(
                    "P1 fleet_active event", False, "no fleet_active event"
                )
            )

        batch_event = FeedEvent.objects.filter(
            kind=FeedEvent.Kind.KILLMAIL_BATCH
        ).first()
        results.append(
            CheckResult(
                "P1 killmail_batch event",
                batch_event is not None,
                getattr(batch_event, "title", "missing"),
            )
        )
        return results

    def _assert_api(self) -> list[CheckResult]:
        client = Client()
        response = client.get("/api/feed/?days=30&limit=10")
        if response.status_code != 200:
            return [
                CheckResult(
                    "GET /api/feed/", False, f"status={response.status_code}"
                )
            ]
        data = response.json()
        items = data.get("items") or []
        kinds = {item.get("kind") for item in items}
        return [
            CheckResult(
                "GET /api/feed/",
                response.status_code == 200 and len(items) > 0,
                f"{len(items)} items kinds={sorted(kinds)}",
            )
        ]

    def _assert_scope(self) -> list[CheckResult]:
        allowlist = set(
            FeedMonitoredSystem.objects.filter(is_active=True).values_list(
                "solar_system_id", flat=True
            )
        )
        out_of_scope = FeedKillmail.objects.exclude(
            solar_system_id__in=allowlist
        ).count()
        return [
            CheckResult(
                "Scope audit",
                out_of_scope == 0,
                f"out_of_allowlist={out_of_scope}",
            )
        ]
