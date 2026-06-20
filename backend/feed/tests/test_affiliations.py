from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from eveonline.client import EsiResponse
from feed.constants import FACTION_MINMATAR
from feed.helpers.affiliations import (
    apply_killmail_affiliations,
    lookup_character_militia_factions,
    populate_unchecked_character_affiliations_batch,
    refresh_character_affiliation,
    refresh_stale_character_affiliations_batch,
)
from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.helpers.killmail_classify import (
    dominant_attacker_faction,
    resolve_attacker_militia_factions,
)
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedCharacterAffiliation
from feed.tests.helpers import make_killmail_payload


def _esi_affiliation_response(*rows: dict) -> EsiResponse:
    return EsiResponse(response_code=200, data=list(rows))


class FeedCharacterAffiliationTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()

    def _recent_killmail_payload(self, killmail_id: int, **kwargs):
        return make_killmail_payload(
            killmail_id,
            killmail_time=timezone.now(),
            **kwargs,
        )

    def test_killmail_apply_sets_militia_tag_eagerly(self):
        apply_killmail_affiliations(
            {
                "attackers": [
                    {
                        "character_id": 1001,
                        "corporation_id": 98000001,
                        "alliance_id": 99000001,
                        "faction_id": FACTION_MINMATAR,
                    }
                ],
                "victim": {},
            }
        )

        row = FeedCharacterAffiliation.objects.get(character_id=1001)
        self.assertEqual(row.faction_id, FACTION_MINMATAR)
        self.assertEqual(row.corporation_id, 98000001)
        self.assertIsNone(row.esi_checked_at)

    def test_killmail_apply_without_tags_creates_row(self):
        apply_killmail_affiliations(
            {
                "attackers": [{"character_id": 1002}],
                "victim": {},
            }
        )

        row = FeedCharacterAffiliation.objects.get(character_id=1002)
        self.assertIsNone(row.faction_id)
        self.assertIsNone(row.esi_checked_at)

    def test_killmail_apply_corp_only(self):
        apply_killmail_affiliations(
            {
                "attackers": [
                    {"character_id": 1003, "corporation_id": 98000001}
                ],
                "victim": {},
            }
        )

        row = FeedCharacterAffiliation.objects.get(character_id=1003)
        self.assertIsNone(row.faction_id)
        self.assertEqual(row.corporation_id, 98000001)
        self.assertIsNone(row.esi_checked_at)

    def test_ingest_applies_killmail_affiliations_eagerly(self):
        payload = self._recent_killmail_payload(
            500001,
            attacker_count=1,
            faction_id=FACTION_MINMATAR,
        )
        upsert_feed_killmail_from_r2z2(payload)

        row = FeedCharacterAffiliation.objects.get(character_id=90000000)
        self.assertEqual(row.faction_id, FACTION_MINMATAR)
        self.assertIsNone(row.esi_checked_at)

    @patch("feed.helpers.affiliations.EsiClient")
    def test_populate_esi_checks_unchecked_rows(self, esi_mock):
        apply_killmail_affiliations(
            {
                "attackers": [
                    {"character_id": 1001, "corporation_id": 98000001}
                ],
                "victim": {},
            }
        )
        esi_mock.return_value.get_character_affiliations.return_value = (
            _esi_affiliation_response(
                {
                    "character_id": 1001,
                    "corporation_id": 98000001,
                    "alliance_id": None,
                    "faction_id": FACTION_MINMATAR,
                }
            )
        )

        updated = populate_unchecked_character_affiliations_batch()
        self.assertEqual(updated, 1)

        row = FeedCharacterAffiliation.objects.get(character_id=1001)
        self.assertEqual(row.faction_id, FACTION_MINMATAR)
        self.assertIsNotNone(row.esi_checked_at)

    @patch("feed.helpers.affiliations.EsiClient")
    def test_populate_marks_non_militia_via_esi(self, esi_mock):
        apply_killmail_affiliations(
            {
                "attackers": [
                    {"character_id": 1002, "corporation_id": 98000001}
                ],
                "victim": {},
            }
        )
        esi_mock.return_value.get_character_affiliations.return_value = (
            _esi_affiliation_response(
                {
                    "character_id": 1002,
                    "corporation_id": 98000001,
                    "alliance_id": None,
                    "faction_id": 500004,
                }
            )
        )

        updated = populate_unchecked_character_affiliations_batch()
        self.assertEqual(updated, 1)

        row = FeedCharacterAffiliation.objects.get(character_id=1002)
        self.assertIsNone(row.faction_id)
        self.assertIsNotNone(row.esi_checked_at)

    @patch("feed.helpers.affiliations.EsiClient")
    def test_populate_leaves_unchecked_on_esi_failure(self, esi_mock):
        apply_killmail_affiliations(
            {
                "attackers": [
                    {"character_id": 1003, "corporation_id": 98000001}
                ],
                "victim": {},
            }
        )
        esi_mock.return_value.get_character_affiliations.return_value = (
            EsiResponse(
                response_code=500,
                data="error",
            )
        )

        updated = populate_unchecked_character_affiliations_batch()
        self.assertEqual(updated, 0)

        row = FeedCharacterAffiliation.objects.get(character_id=1003)
        self.assertIsNone(row.esi_checked_at)

    def test_killmail_does_not_overwrite_esi_checked_militia(self):
        checked_at = timezone.now()
        FeedCharacterAffiliation.objects.create(
            character_id=1004,
            faction_id=None,
            esi_checked_at=checked_at,
        )
        apply_killmail_affiliations(
            {
                "attackers": [
                    {
                        "character_id": 1004,
                        "corporation_id": 98000001,
                        "faction_id": FACTION_MINMATAR,
                    }
                ],
                "victim": {},
            }
        )

        row = FeedCharacterAffiliation.objects.get(character_id=1004)
        self.assertIsNone(row.faction_id)
        self.assertEqual(row.esi_checked_at, checked_at)

    def test_lookup_uses_populated_affiliations(self):
        FeedCharacterAffiliation.objects.create(
            character_id=101,
            faction_id=FACTION_MINMATAR,
            corporation_id=98000001,
        )
        FeedCharacterAffiliation.objects.create(
            character_id=102,
            faction_id=FACTION_MINMATAR,
            esi_checked_at=timezone.now(),
            corporation_id=98000001,
        )

        killmails = [
            {
                "killmail_id": 1,
                "attackers": [
                    {"character_id": 100, "corporation_id": 98000001},
                    {"character_id": 101, "corporation_id": 98000001},
                    {"character_id": 102, "corporation_id": 98000001},
                    {
                        "character_id": 200,
                        "corporation_id": 98000002,
                        "faction_id": 500003,
                    },
                ],
                "victim": {},
            }
        ]

        factions = resolve_attacker_militia_factions(killmails)
        self.assertEqual(factions[101], FACTION_MINMATAR)
        self.assertEqual(
            lookup_character_militia_factions({101, 102}),
            {101: FACTION_MINMATAR, 102: FACTION_MINMATAR},
        )

    def test_corp_bloc_uses_populated_affiliations_in_mixed_fight(self):
        enlisted_corp = 98000001
        for char_id in range(100, 106):
            FeedCharacterAffiliation.objects.create(
                character_id=char_id,
                faction_id=FACTION_MINMATAR,
                corporation_id=enlisted_corp,
            )

        attackers = [
            {"character_id": char_id, "corporation_id": enlisted_corp}
            for char_id in range(100, 106)
        ] + [
            {
                "character_id": 200 + i,
                "corporation_id": 98000002,
                "faction_id": 500003,
            }
            for i in range(8)
        ]
        killmails = [{"killmail_id": 1, "attackers": attackers, "victim": {}}]
        self.assertEqual(
            dominant_attacker_faction(killmails),
            FACTION_MINMATAR,
        )

    @patch("feed.helpers.affiliations.EsiClient")
    def test_refresh_updates_stale_esi_checked_row(self, esi_mock):
        old_time = timezone.now() - timedelta(days=10)
        FeedCharacterAffiliation.objects.create(
            character_id=1001,
            faction_id=FACTION_MINMATAR,
            esi_checked_at=old_time,
        )
        esi_mock.return_value.get_character_affiliations.return_value = (
            _esi_affiliation_response(
                {
                    "character_id": 1001,
                    "corporation_id": 98000001,
                    "alliance_id": None,
                    "faction_id": FACTION_MINMATAR,
                }
            )
        )

        self.assertTrue(refresh_character_affiliation(1001))

        row = FeedCharacterAffiliation.objects.get(character_id=1001)
        self.assertGreater(row.esi_checked_at, old_time)

    @patch("feed.helpers.affiliations.EsiClient")
    def test_refresh_skips_unchecked_rows(self, esi_mock):
        FeedCharacterAffiliation.objects.create(
            character_id=1005,
            faction_id=FACTION_MINMATAR,
        )

        updated = refresh_stale_character_affiliations_batch()
        self.assertEqual(updated, 0)
        esi_mock.return_value.get_character_affiliations.assert_not_called()
