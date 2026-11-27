from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from exits.models import Departure
from taskboard import sync
from taskboard.models import Task, TeamKind
from taskboard.rules import RULES
from taskboard.teams import Membership


def pilot(name, character_id, corporation_id=None):
    user = User.objects.create(username=name)
    character = EveCharacter.objects.create(
        character_id=character_id,
        character_name=name,
        user=user,
        corporation_id=corporation_id,
    )
    return user, character


class DepartureTaskTest(TestCase):
    def setUp(self):
        fl33t = EveAlliance.objects.create(
            alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
            name="Minmatar Fleet Alliance",
        )
        self.ceo, ceo_character = pilot("ceo", 2112000001, 98000001)
        self.director, director_character = pilot(
            "director", 2112000002, 98000001
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Example Corp",
            alliance=fl33t,
            track_exits=True,
            ceo=ceo_character,
        )
        self.corporation.directors.add(director_character)

    def _confirmed(self, character_id, corporation=None):
        now = timezone.now()
        return Departure.objects.create(
            corporation=corporation or self.corporation,
            character_id=character_id,
            first_missing_at=now,
            status="confirmed",
            confirmed_at=now,
            kind="exit",
        )

    def _items(self):
        return RULES["exit_departures"].collect(None)

    def test_one_task_per_corporation(self):
        self._confirmed(1)
        self._confirmed(2)
        [item] = self._items()
        self.assertEqual(item.title, "Tell us why 2 pilots left")
        self.assertEqual(item.team_kind, TeamKind.CORPORATION)
        self.assertEqual(item.team_id, 98000001)
        self.assertEqual(item.team_role, "ceo")
        self.assertEqual(
            item.link_url, "/alliance/corporations/98000001/#departures"
        )

    def test_one_pilot_is_singular(self):
        self._confirmed(1)
        [item] = self._items()
        self.assertEqual(item.title, "Tell us why 1 pilot left")

    def test_task_closes_when_all_answered(self):
        first = self._confirmed(1)
        second = self._confirmed(2)
        sync.sync_rule(RULES["exit_departures"])
        task = Task.objects.get(rule="exit_departures")
        self.assertEqual(task.status, Task.STATUS_OPEN)
        Departure.objects.filter(pk__in=[first.pk, second.pk]).update(
            reason="kicked_inactive", can_rejoin=True
        )
        sync.sync_rule(RULES["exit_departures"])
        task.refresh_from_db()
        self.assertEqual(task.status, Task.STATUS_DONE)

    def test_director_cannot_act(self):
        membership = Membership(self.director)
        self.assertFalse(
            membership.can_act(TeamKind.CORPORATION, 98000001, "ceo")
        )
        self.assertTrue(
            Membership(self.ceo).can_act(TeamKind.CORPORATION, 98000001, "ceo")
        )

    def test_ceo_role_outside_member_corporations(self):
        outsider, outsider_ceo = pilot("mec ceo", 2112000003, 98000002)
        mec = EveCorporation.objects.create(
            corporation_id=98000002,
            name="Mining Corp",
            track_exits=True,
            ceo=outsider_ceo,
        )
        self._confirmed(5, corporation=mec)
        self.assertTrue(
            Membership(outsider).can_act(TeamKind.CORPORATION, 98000002, "ceo")
        )

    def test_superuser_ceo_can_act_outside_member_corporations(self):
        outsider, outsider_ceo = pilot("admin ceo", 2112000004, 98000003)
        outsider.is_superuser = True
        outsider.save()
        EveCorporation.objects.create(
            corporation_id=98000003,
            name="Other Tracked",
            track_exits=True,
            ceo=outsider_ceo,
        )
        self.assertTrue(
            Membership(outsider).can_act(TeamKind.CORPORATION, 98000003, "ceo")
        )
