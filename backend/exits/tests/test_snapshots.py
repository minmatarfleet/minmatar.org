from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from exits.helpers.snapshots import record_members, stop_tracking
from exits.models import Departure, MemberSnapshot


class RecordMembersTest(TestCase):
    def setUp(self):
        self.alliance = EveAlliance.objects.create(
            alliance_id=99000001, name="Alliance A"
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Example Corp",
            alliance=self.alliance,
            track_exits=True,
        )
        self.now = timezone.now()

    def _snapshot(self, member_ids, alliance_id=99000001):
        return MemberSnapshot.objects.create(
            corporation=self.corporation,
            member_ids=member_ids,
            alliance_id=alliance_id,
            taken_at=self.now - timedelta(hours=1),
        )

    def _pending(self, character_id):
        return Departure.objects.create(
            corporation=self.corporation,
            character_id=character_id,
            first_missing_at=self.now - timedelta(hours=1),
        )

    def test_first_sync_only_stores(self):
        result = record_members(self.corporation, [1, 2], self.now)
        self.assertEqual(result.skipped, "first_sync")
        self.assertFalse(Departure.objects.exists())
        self.assertEqual(
            MemberSnapshot.objects.get(
                corporation=self.corporation
            ).member_ids,
            [1, 2],
        )

    def test_missing_member_opens_departure(self):
        self._snapshot([1, 2, 3])
        result = record_members(self.corporation, [1, 2], self.now)
        self.assertEqual(result.skipped, "")
        self.assertEqual(result.left, {3})
        departure = Departure.objects.get()
        self.assertEqual(departure.character_id, 3)
        self.assertEqual(departure.status, "pending")
        self.assertEqual(departure.first_missing_at, self.now)

    def test_departure_carries_the_account(self):
        user = User.objects.create(username="pilot")
        EveCharacter.objects.create(
            character_id=3, character_name="Three", user=user
        )
        self._snapshot([1, 2, 3])
        record_members(self.corporation, [1, 2], self.now)
        self.assertEqual(Departure.objects.get().user, user)

    def test_still_missing_does_not_open_a_second_departure(self):
        self._snapshot([1, 2])
        self._pending(3)
        record_members(self.corporation, [1, 2], self.now)
        self.assertEqual(Departure.objects.count(), 1)

    def test_back_within_grace_is_dropped(self):
        self._snapshot([1, 2])
        departure = self._pending(3)
        record_members(self.corporation, [1, 2, 3], self.now)
        departure.refresh_from_db()
        self.assertEqual(departure.status, "dropped")

    def test_empty_member_list_is_skipped(self):
        self._snapshot([1, 2])
        result = record_members(self.corporation, [], self.now)
        self.assertEqual(result.skipped, "empty")
        self.assertFalse(Departure.objects.exists())
        self.assertEqual(
            MemberSnapshot.objects.get(
                corporation=self.corporation
            ).member_ids,
            [1, 2],
        )

    def test_alliance_changed_resets(self):
        self._snapshot([1, 2, 3])
        departure = self._pending(4)
        self.corporation.alliance = EveAlliance.objects.create(
            alliance_id=99000002, name="Alliance B"
        )
        self.corporation.save()
        result = record_members(self.corporation, [1], self.now)
        self.assertEqual(result.skipped, "alliance_changed")
        departure.refresh_from_db()
        self.assertEqual(departure.status, "dropped")
        self.assertEqual(Departure.objects.count(), 1)
        snapshot = MemberSnapshot.objects.get(corporation=self.corporation)
        self.assertEqual(snapshot.member_ids, [1])
        self.assertEqual(snapshot.alliance_id, 99000002)

    def test_joined_members_are_returned(self):
        self._snapshot([1])
        result = record_members(self.corporation, [1, 4], self.now)
        self.assertEqual(result.joined, {4})
        self.assertEqual(result.left, set())

    def test_stop_tracking_drops_pending(self):
        self._snapshot([1, 2])
        departure = self._pending(3)
        stop_tracking(self.corporation)
        departure.refresh_from_db()
        self.assertEqual(departure.status, "dropped")
        self.assertFalse(MemberSnapshot.objects.exists())
