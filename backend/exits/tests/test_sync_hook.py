from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.utils import timezone

from eveonline.admin import EveCorporationAdmin
from eveonline.helpers.corporations.update import (
    update_corporation_members_and_roles,
)
from eveonline.models import EveCharacter, EveCorporation
from eveonline.tasks.corporations import (
    update_corporation,
    update_corporations,
)
from exits.models import Departure, MemberSnapshot

UPDATE = "eveonline.helpers.corporations.update"
TASKS = "eveonline.tasks.corporations"


def esi_response(success, results=None):
    response = MagicMock()
    response.success.return_value = success
    response.results.return_value = results
    response.response_code = 200 if success else 502
    return response


class MemberSyncHookTest(TestCase):
    def setUp(self):
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001, name="Mining Corp", track_exits=True
        )
        self.director = EveCharacter.objects.create(
            character_id=2112000099, character_name="Director"
        )

    def _sync(self, members_response):
        client = MagicMock()
        client.get_corporation_members.return_value = members_response
        client.get_corporation_roles.return_value = esi_response(False)
        with patch(
            f"{UPDATE}.get_director_with_scope", return_value=self.director
        ), patch(f"{UPDATE}.EsiClient", return_value=client), patch(
            "exits.helpers.snapshots.record_members"
        ) as record:
            update_corporation_members_and_roles(
                self.corporation.corporation_id
            )
        return record

    def test_tracked_public_corporation_is_synced(self):
        self.assertEqual(self.corporation.type, "public")
        record = self._sync(esi_response(True, [1, 2]))
        record.assert_called_once()
        self.assertEqual(record.call_args.args[0], self.corporation)
        self.assertEqual(record.call_args.args[1], [1, 2])

    def test_untracked_corporation_is_not_recorded(self):
        self.corporation.track_exits = False
        self.corporation.save()
        record = self._sync(esi_response(True, [1, 2]))
        record.assert_not_called()

    def test_failed_members_call_records_nothing(self):
        record = self._sync(esi_response(False))
        record.assert_not_called()


class UpdateCorporationTaskTest(TestCase):
    def test_tracked_militia_corporation_reaches_the_member_sync(self):
        corporation = EveCorporation.objects.create(
            corporation_id=98000002, name="Militia Corp", track_exits=True
        )
        directors = MagicMock()
        directors.__getitem__.side_effect = lambda key: True
        with patch(f"{TASKS}.refresh_corporation_populate"), patch(
            f"{TASKS}.resolve_directors_by_scope", return_value=directors
        ), patch(
            f"{TASKS}.refresh_corporation_members_and_roles"
        ) as members, patch(
            f"{TASKS}.refresh_corporation_contracts"
        ), patch(
            f"{TASKS}.refresh_corporation_industry_jobs"
        ), patch(
            f"{TASKS}.refresh_corporation_blueprints"
        ), patch(
            f"{TASKS}.refresh_corporation_wallet_journal"
        ):
            update_corporation(corporation.corporation_id)
        members.assert_called_once_with(corporation.corporation_id)

    def test_tracked_corporation_outside_the_alliance_is_queued(self):
        corporation = EveCorporation.objects.create(
            corporation_id=98000003, name="Tracked Corp", track_exits=True
        )
        with patch(f"{TASKS}.member_corporations", return_value=[]), patch(
            f"{TASKS}.update_corporation.apply_async"
        ) as queued:
            update_corporations()
        queued.assert_called_once_with(args=[corporation.corporation_id])


class UntickTrackExitsTest(TestCase):
    def test_unticking_track_exits_stops_tracking(self):
        corporation = EveCorporation.objects.create(
            corporation_id=98000004, name="Example Corp", track_exits=True
        )
        MemberSnapshot.objects.create(
            corporation=corporation, member_ids=[1], taken_at=timezone.now()
        )
        departure = Departure.objects.create(
            corporation=corporation,
            character_id=3,
            first_missing_at=timezone.now(),
        )
        corporation.track_exits = False
        form = MagicMock(changed_data=["track_exits"])
        EveCorporationAdmin(EveCorporation, AdminSite()).save_model(
            MagicMock(), corporation, form, True
        )
        departure.refresh_from_db()
        self.assertEqual(departure.status, "dropped")
        self.assertFalse(MemberSnapshot.objects.exists())
