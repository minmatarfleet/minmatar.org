"""Corporation projects: ESI listing, detail and contributors into the DB."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from eveuniverse.models import EveCategory, EveFaction, EveGroup, EveType

from eveonline.client import EsiResponse
from eveonline.helpers.corporations import projects
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveCorporationProject,
)

PROJECT_ID = "3868eaed-8278-4cb7-9709-7d7de9c20dc7"
OTHER_ID = "11111111-2222-3333-4444-555555555555"


def listing_row(project_id=PROJECT_ID, modified="2026-10-01T10:00:00Z"):
    return {
        "id": project_id,
        "name": "Kill Amarr frigates",
        "state": "Active",
        "last_modified": modified,
        "progress": {"current": 4, "desired": 20},
        "reward": {"initial": 100_000_000.0, "remaining": 80_000_000.0},
    }


DETAIL = {
    "id": PROJECT_ID,
    "name": "Kill Amarr frigates",
    "state": "Active",
    "last_modified": "2026-10-01T10:00:00Z",
    "progress": {"current": 4, "desired": 20},
    "reward": {"initial": 100_000_000.0, "remaining": 80_000_000.0},
    "creator": {"id": 9001, "name": "Director Dan"},
    "details": {
        "description": "Frigates in the warzone",
        "career": "Enforcer",
        "created": "2026-09-30T00:00:00Z",
        "expires": "2026-10-30T00:00:00Z",
    },
    "contribution": {
        "reward_per_contribution": 5_000_000.0,
        "participation_limit": 5,
    },
    "configuration": {
        "destroy_ship": {
            "identities": [{"faction_id": 500003}],
            "ships": [{"type_id": 587}, {"type_id": 999999}],
            "locations": [{"solar_system_id": 30003069}],
        }
    },
}

CONTRIBUTORS = [
    {"id": 9101, "name": "Pilot One", "contributed": 3},
    {"id": 9102, "name": "Pilot Two", "contributed": 1},
]


class FakeEsi:
    def __init__(self, listing, detail=None, contributors=None):
        self.listing = listing
        self.detail = detail or DETAIL
        self.contributors = contributors or CONTRIBUTORS
        self.detail_calls = 0
        self.contributor_calls = 0

    def get_corporation_projects(self, corporation_id):
        return EsiResponse(0, data=self.listing)

    def get_corporation_project(self, corporation_id, project_id):
        self.detail_calls += 1
        if isinstance(self.detail, int):
            return EsiResponse(self.detail)
        return EsiResponse(0, data=self.detail)

    def get_corporation_project_contributors(self, corporation_id, project_id):
        self.contributor_calls += 1
        if isinstance(self.contributors, int):
            return EsiResponse(self.contributors)
        return EsiResponse(0, data=self.contributors)


class CorporationProjectSyncTests(TestCase):
    def setUp(self):
        cache.clear()
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001, name="Rattini Tribe"
        )
        self.director = EveCharacter.objects.create(
            character_id=9001, character_name="Director Dan"
        )
        category, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=25,
            defaults={
                "name": "Frigate",
                "published": True,
                "eve_category": category,
            },
        )
        EveType.objects.create(
            id=587, name="Rifter", published=True, eve_group=group
        )
        EveFaction.objects.create(
            id=500003,
            name="Amarr Empire",
            description="Amarr",
            is_unique=True,
            size_factor=1.0,
            station_count=1,
            station_system_count=1,
        )

    def _sync(self, esi, holder="director"):
        holder = self.director if holder == "director" else holder
        with patch.object(
            projects, "projects_scope_holder", return_value=holder
        ), patch.object(projects, "esi_for", return_value=esi):
            return projects.sync_corporation_projects(
                self.corporation.corporation_id
            )

    def test_stores_project_detail_and_contributors(self):
        esi = FakeEsi([listing_row()])
        self.assertEqual("ok", self._sync(esi))

        project = EveCorporationProject.objects.get()
        self.assertEqual("destroy_ship", project.kind)
        self.assertEqual("Frigates in the warzone", project.description)
        self.assertEqual("Director Dan", project.creator_name)
        self.assertEqual(5_000_000.0, project.reward_per_contribution)
        self.assertEqual(80_000_000.0, project.reward_remaining)
        self.assertIsNotNone(project.expires)
        self.assertIsNotNone(project.detail_synced_at)
        self.assertEqual(
            [("Pilot One", 3), ("Pilot Two", 1)],
            [
                (row.character_name, row.contributed)
                for row in project.contributors.all()
            ],
        )
        # Only names we hold locally; the unknown type is left out.
        self.assertEqual(
            [
                {"kind": "ships", "names": ["Rifter"]},
                {"kind": "identities", "names": ["Amarr Empire"]},
            ],
            [
                target
                for target in project.targets
                if target["kind"] in ("ships", "identities")
            ],
        )
        self.assertIsNotNone(projects.last_synced(98000001))

    def test_unchanged_project_skips_detail(self):
        self._sync(FakeEsi([listing_row()]))
        esi = FakeEsi([listing_row()])
        self._sync(esi)
        self.assertEqual(0, esi.detail_calls)

        moved = FakeEsi([listing_row(modified="2026-10-02T10:00:00Z")])
        self._sync(moved)
        self.assertEqual(1, moved.detail_calls)

    def test_failed_contributors_keep_old_rows_and_retry(self):
        self._sync(FakeEsi([listing_row()]))
        later = listing_row(modified="2026-10-02T10:00:00Z")
        self._sync(FakeEsi([later], contributors=403))

        project = EveCorporationProject.objects.get()
        self.assertEqual(2, project.contributors.count())
        retry = FakeEsi([later])
        self._sync(retry)
        self.assertEqual(1, retry.contributor_calls)

    def test_deleted_projects_are_not_fetched(self):
        row = listing_row()
        row["state"] = "Deleted"
        esi = FakeEsi([row])
        self._sync(esi)
        self.assertEqual(0, esi.detail_calls)
        self.assertEqual("Deleted", EveCorporationProject.objects.get().state)

    def test_rate_limit_stops_the_run(self):
        esi = FakeEsi(
            [listing_row(), listing_row(project_id=OTHER_ID)], detail=429
        )
        self.assertEqual("esi_error", self._sync(esi))
        self.assertEqual(1, esi.detail_calls)

    def test_no_token(self):
        self.assertEqual("no_token", self._sync(FakeEsi([]), holder=None))
        self.assertFalse(EveCorporationProject.objects.exists())

    def test_sync_clears_the_refresh_flag(self):
        self.assertTrue(projects.mark_refreshing(98000001))
        self.assertFalse(projects.mark_refreshing(98000001))
        self._sync(FakeEsi([]))
        self.assertFalse(projects.is_refreshing(98000001))

    def test_unknown_configuration_keeps_its_type(self):
        kind, inner = projects.split_configuration(
            {"unknown": {"type": "future_thing", "data": None}}
        )
        self.assertEqual("future_thing", kind)
        self.assertEqual("future_thing", inner["type"])
