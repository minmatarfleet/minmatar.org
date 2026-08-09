"""Tests for character corporation history sync and enrichment."""

from datetime import timedelta
from unittest.mock import patch

import factory
from django.db.models import signals
from django.test import override_settings
from django.utils import timezone
from esi.exceptions import ESIErrorLimitException

from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.helpers.characters.corporation_history import (
    alliance_id_at,
    character_corporation_history_is_stale,
    ensure_corporation_alliance_history,
    sync_character_corporation_history,
)
from eveonline.helpers.characters.public_data import (
    update_character_public_data,
)
from eveonline.models import (
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCorporationAllianceHistory,
)


def _history_response(rows):
    return EsiResponse(response_code=200, data=rows)


class AllianceIdAtTests(TestCase):
    def test_picks_alliance_interval_containing_join(self):
        rows = [
            EveCorporationAllianceHistory(
                corporation_id=1,
                record_id=3,
                alliance_id=99012009,
                start_date=timezone.now() - timedelta(days=10),
            ),
            EveCorporationAllianceHistory(
                corporation_id=1,
                record_id=2,
                alliance_id=99011978,
                start_date=timezone.now() - timedelta(days=100),
            ),
            EveCorporationAllianceHistory(
                corporation_id=1,
                record_id=1,
                alliance_id=None,
                start_date=timezone.now() - timedelta(days=365),
            ),
        ]
        join = timezone.now() - timedelta(days=50)
        self.assertEqual(99011978, alliance_id_at(rows, join))


class CorporationHistorySyncTests(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def setUp(self):
        self.character = EveCharacter.objects.create(
            character_id=91000001,
            character_name="History Pilot",
            corporation_id=2001,
            faction_id=500002,
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_ttl_skip_when_synced_recently(self):
        self.character.corporation_history_synced_at = timezone.now()
        self.character.save(update_fields=["corporation_history_synced_at"])
        EveCharacterCorporationHistory.objects.create(
            character=self.character,
            record_id=1,
            corporation_id=2001,
            start_date=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(
            character_corporation_history_is_stale(self.character)
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_never_synced_skipped_when_include_false(self):
        self.assertIsNone(self.character.corporation_history_synced_at)
        self.assertTrue(character_corporation_history_is_stale(self.character))
        self.assertFalse(
            character_corporation_history_is_stale(
                self.character, include_never_synced=False
            )
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_stale_when_corporation_changed(self):
        self.character.corporation_history_synced_at = timezone.now()
        self.character.corporation_id = 3001
        self.character.save()
        EveCharacterCorporationHistory.objects.create(
            character=self.character,
            record_id=1,
            corporation_id=2001,
            start_date=timezone.now() - timedelta(days=1),
        )
        self.assertTrue(character_corporation_history_is_stale(self.character))

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.corporation_history.esi_public")
    def test_sync_upserts_and_resolves_alliance(self, esi_public):
        join_old = timezone.now() - timedelta(days=200)
        join_new = timezone.now() - timedelta(days=30)
        client = esi_public.return_value
        client.get_character_corporation_history.return_value = (
            _history_response(
                [
                    {
                        "record_id": 10,
                        "corporation_id": 2001,
                        "start_date": join_new.isoformat(),
                    },
                    {
                        "record_id": 9,
                        "corporation_id": 1001,
                        "start_date": join_old.isoformat(),
                    },
                ]
            )
        )
        client.get_corporation_alliance_history.side_effect = [
            _history_response(
                [
                    {
                        "record_id": 1,
                        "alliance_id": 99011978,
                        "start_date": (
                            timezone.now() - timedelta(days=400)
                        ).isoformat(),
                    },
                    {
                        "record_id": 2,
                        "alliance_id": 99012009,
                        "start_date": (
                            timezone.now() - timedelta(days=50)
                        ).isoformat(),
                    },
                ]
            ),
            _history_response(
                [
                    {
                        "record_id": 1,
                        "alliance_id": 99011978,
                        "start_date": (
                            timezone.now() - timedelta(days=400)
                        ).isoformat(),
                    },
                ]
            ),
        ]

        self.assertTrue(sync_character_corporation_history(self.character))

        rows = list(
            EveCharacterCorporationHistory.objects.filter(
                character=self.character
            ).order_by("record_id")
        )
        self.assertEqual(2, len(rows))
        self.assertEqual(1001, rows[0].corporation_id)
        self.assertEqual(99011978, rows[0].alliance_id)
        self.assertEqual(2001, rows[1].corporation_id)
        self.assertEqual(99012009, rows[1].alliance_id)
        self.assertEqual(500002, rows[1].faction_id)
        self.character.refresh_from_db()
        self.assertIsNotNone(self.character.corporation_history_synced_at)

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.corporation_history.esi_public")
    def test_faction_null_when_no_matching_source(self, esi_public):
        join = timezone.now() - timedelta(days=30)
        self.character.faction_id = None
        self.character.save(update_fields=["faction_id"])
        client = esi_public.return_value
        client.get_character_corporation_history.return_value = (
            _history_response(
                [
                    {
                        "record_id": 1,
                        "corporation_id": 2001,
                        "start_date": join.isoformat(),
                    }
                ]
            )
        )
        client.get_corporation_alliance_history.return_value = (
            _history_response(
                [
                    {
                        "record_id": 1,
                        "alliance_id": 111,
                        "start_date": (
                            timezone.now() - timedelta(days=100)
                        ).isoformat(),
                    }
                ]
            )
        )

        sync_character_corporation_history(self.character)
        row = EveCharacterCorporationHistory.objects.get(
            character=self.character
        )
        self.assertEqual(111, row.alliance_id)
        self.assertIsNone(row.faction_id)

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.corporation_history.esi_public")
    def test_faction_not_overwritten_on_resync(self, esi_public):
        join = timezone.now() - timedelta(days=30)
        EveCharacterCorporationHistory.objects.create(
            character=self.character,
            record_id=1,
            corporation_id=2001,
            start_date=join,
            alliance_id=99011978,
            faction_id=500001,
        )
        client = esi_public.return_value
        client.get_character_corporation_history.return_value = (
            _history_response(
                [
                    {
                        "record_id": 1,
                        "corporation_id": 2001,
                        "start_date": join.isoformat(),
                    }
                ]
            )
        )
        client.get_corporation_alliance_history.return_value = (
            _history_response(
                [
                    {
                        "record_id": 1,
                        "alliance_id": 99011978,
                        "start_date": (
                            timezone.now() - timedelta(days=100)
                        ).isoformat(),
                    }
                ]
            )
        )

        sync_character_corporation_history(self.character, force=True)
        row = EveCharacterCorporationHistory.objects.get(
            character=self.character, record_id=1
        )
        self.assertEqual(500001, row.faction_id)

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.corporation_history.esi_public")
    def test_alliance_cache_avoids_second_esi(self, esi_public):
        client = esi_public.return_value
        client.get_corporation_alliance_history.return_value = (
            _history_response(
                [
                    {
                        "record_id": 1,
                        "alliance_id": 99011978,
                        "start_date": (
                            timezone.now() - timedelta(days=10)
                        ).isoformat(),
                    }
                ]
            )
        )
        ensure_corporation_alliance_history(555)
        ensure_corporation_alliance_history(555)
        self.assertEqual(1, client.get_corporation_alliance_history.call_count)

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.corporation_history.esi_public")
    def test_orphan_record_removed(self, esi_public):
        EveCharacterCorporationHistory.objects.create(
            character=self.character,
            record_id=99,
            corporation_id=9999,
            start_date=timezone.now() - timedelta(days=5),
        )
        join = timezone.now() - timedelta(days=1)
        client = esi_public.return_value
        client.get_character_corporation_history.return_value = (
            _history_response(
                [
                    {
                        "record_id": 1,
                        "corporation_id": 2001,
                        "start_date": join.isoformat(),
                    }
                ]
            )
        )
        client.get_corporation_alliance_history.return_value = (
            _history_response([])
        )

        sync_character_corporation_history(self.character, force=True)
        self.assertFalse(
            EveCharacterCorporationHistory.objects.filter(
                character=self.character, record_id=99
            ).exists()
        )

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.corporation_history.esi_public")
    def test_history_error_skips_without_raising(self, esi_public):
        esi_public.return_value.get_character_corporation_history.return_value = EsiResponse(
            response_code=500, response="boom"
        )
        self.assertFalse(sync_character_corporation_history(self.character))
        self.assertIsNone(self.character.corporation_history_synced_at)

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.corporation_history.esi_public")
    def test_error_limit_reraise(self, esi_public):
        esi_public.return_value.get_character_corporation_history.return_value = EsiResponse(
            response_code=420,
            response=ESIErrorLimitException(reset=12),
        )
        with self.assertRaises(ESIErrorLimitException):
            sync_character_corporation_history(self.character)

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch(
        "eveonline.helpers.characters.public_data.sync_character_corporation_history"
    )
    @patch("eveonline.helpers.characters.public_data.esi_public")
    def test_public_data_skips_history_without_corp_change(
        self, esi_public, sync_history
    ):
        esi_public.return_value.get_character_public_data.return_value = (
            EsiResponse(
                response_code=200,
                data={
                    "name": "History Pilot",
                    "corporation_id": 2001,
                    "security_status": 1.0,
                },
            )
        )
        update_character_public_data(self.character.character_id)
        sync_history.assert_not_called()

    @override_settings(ALLOW_LIVE_ESI_IN_TESTS=True)
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch(
        "eveonline.helpers.characters.public_data.sync_character_corporation_history"
    )
    @patch("eveonline.helpers.characters.public_data.esi_public")
    def test_public_data_syncs_history_on_corp_change(
        self, esi_public, sync_history
    ):
        esi_public.return_value.get_character_public_data.return_value = (
            EsiResponse(
                response_code=200,
                data={
                    "name": "History Pilot",
                    "corporation_id": 9999,
                    "security_status": 1.0,
                },
            )
        )
        update_character_public_data(self.character.character_id)
        sync_history.assert_called_once()
