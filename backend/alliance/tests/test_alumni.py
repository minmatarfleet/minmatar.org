"""Alumni status: the CEO's write-up, the Discord DM, who may grant and undo
it, and the places alumni stop counting."""

from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import Client

from alliance.helpers.status_change import alumni_message
from app.test import TestCase
from app.testing import make_token
from discord.models import DiscordUser
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from groups.models import UserCommunityStatus, UserCommunityStatusHistory
from taskboard.services import is_paused

CORP_ID = 98000001
BASE = f"/api/eveonline/corporations/corporations/{CORP_ID}/members/2001"
STATUS_URL = f"{BASE}/status"
INSIGHTS_URL = f"{BASE}/insights"
WRITE_UP = "Ran the Tuesday roam for three years and trained half of FOSFO."


def _discord_signals():
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import group_post_save, user_group_changed

    return (
        (
            django_signals.m2m_changed,
            user_group_changed,
            User.groups.through,
            "user_group_changed",
        ),
        (django_signals.post_save, group_post_save, Group, "group_post_save"),
    )


def setUpModule():
    # A status change syncs community groups, which would create Discord roles.
    for signal, receiver, sender, uid in _discord_signals():
        signal.disconnect(receiver, sender=sender, dispatch_uid=uid)


def tearDownModule():
    for signal, receiver, sender, uid in _discord_signals():
        signal.connect(receiver, sender=sender, dispatch_uid=uid)


@patch("alliance.helpers.status_change.queue_dm")
class AlumniFromRosterTestCase(TestCase):
    def setUp(self):
        super().setUp()
        alliance = EveAlliance.objects.create(
            alliance_id=99011978, name="Minmatar Fleet Alliance", ticker="MFA"
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=CORP_ID,
            name="Fosfo Test",
            ticker="FOSFO",
            alliance=alliance,
        )
        self.character = EveCharacter.objects.create(
            character_id=2001,
            character_name="Vosk Arran",
            user=self.user,
            corporation_id=CORP_ID,
        )
        set_primary_character(self.user, self.character)
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ACTIVE
        )
        self.director = User.objects.create(username="director")
        self.corporation.directors.add(
            EveCharacter.objects.create(
                character_id=2002,
                character_name="Director",
                user=self.director,
                corporation_id=CORP_ID,
            )
        )
        self.ceo = User.objects.create(username="ceo")
        boss = EveCharacter.objects.create(
            character_id=2004,
            character_name="Boss",
            user=self.ceo,
            corporation_id=CORP_ID,
        )
        set_primary_character(self.ceo, boss)
        self.corporation.ceo = boss
        self.corporation.save()
        self.client = Client()

    def _post(self, user, action, reason=""):
        return self.client.post(
            STATUS_URL,
            data={"action": action, "reason": reason},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {make_token(user)}",
        )

    def _status(self):
        return UserCommunityStatus.objects.get(user=self.user).status

    def test_ceo_makes_member_alumni_with_a_write_up(self, queue_dm):
        DiscordUser.objects.create(id=4242, discord_tag="vosk", user=self.user)
        response = self._post(self.ceo, "alumni", WRITE_UP)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"community_status": "alumni"})
        self.assertEqual(self._status(), "alumni")
        change = UserCommunityStatusHistory.objects.filter(
            user=self.user, to_status="alumni"
        ).first()
        self.assertEqual(change.changed_by, self.ceo)
        self.assertEqual(change.reason, WRITE_UP)
        self.assertEqual(
            set(self.user.groups.values_list("name", flat=True)), {"Alumni"}
        )
        queue_dm.assert_called_once()
        self.assertEqual(queue_dm.call_args.args[0], 4242)
        message = queue_dm.call_args.kwargs["message"]
        self.assertIn("Vosk Arran", message)
        self.assertIn("Boss wrote", message)
        self.assertIn(f"> {WRITE_UP}", message)

    def test_alumni_needs_a_write_up(self, queue_dm):
        response = self._post(self.ceo, "alumni", "   ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._status(), "active")
        queue_dm.assert_not_called()

    def test_write_up_has_a_limit(self, queue_dm):
        response = self._post(self.ceo, "alumni", "x" * 1001)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._status(), "active")

    def test_on_leave_member_can_become_alumni(self, queue_dm):
        UserCommunityStatus.objects.filter(user=self.user).update(
            status="on_leave"
        )
        data = self.client.get(
            INSIGHTS_URL, HTTP_AUTHORIZATION=f"Bearer {make_token(self.ceo)}"
        ).json()
        self.assertEqual(data["status_actions"], ["restore", "alumni"])
        self.assertEqual(
            self._post(self.ceo, "alumni", WRITE_UP).status_code, 200
        )
        self.assertEqual(self._status(), "alumni")

    def test_no_discord_link_still_makes_alumni(self, queue_dm):
        self.assertEqual(
            self._post(self.ceo, "alumni", WRITE_UP).status_code, 200
        )
        self.assertEqual(self._status(), "alumni")
        queue_dm.assert_not_called()

    def test_director_cannot_make_or_undo_alumni(self, queue_dm):
        data = self.client.get(
            INSIGHTS_URL,
            HTTP_AUTHORIZATION=f"Bearer {make_token(self.director)}",
        ).json()
        self.assertNotIn("alumni", data["status_actions"])
        self.assertEqual(
            self._post(self.director, "alumni", WRITE_UP).status_code, 403
        )
        UserCommunityStatus.objects.filter(user=self.user).update(
            status="alumni"
        )
        data = self.client.get(
            INSIGHTS_URL,
            HTTP_AUTHORIZATION=f"Bearer {make_token(self.director)}",
        ).json()
        self.assertEqual(data["status_actions"], [])
        self.assertEqual(self._post(self.director, "restore").status_code, 403)
        self.assertEqual(self._status(), "alumni")

    def test_ceo_restores_alumni_to_active(self, queue_dm):
        self._post(self.ceo, "alumni", WRITE_UP)
        data = self.client.get(
            INSIGHTS_URL, HTTP_AUTHORIZATION=f"Bearer {make_token(self.ceo)}"
        ).json()
        self.assertEqual(data["status_actions"], ["restore"])
        self.assertEqual(self._post(self.ceo, "restore").status_code, 200)
        self.assertEqual(self._status(), "active")
        self.assertEqual(
            self._post(self.ceo, "alumni", WRITE_UP).status_code, 200
        )

    def test_pilot_without_status_row_is_offered_alumni_only(self, queue_dm):
        UserCommunityStatus.objects.filter(user=self.user).delete()
        data = self.client.get(
            INSIGHTS_URL, HTTP_AUTHORIZATION=f"Bearer {make_token(self.ceo)}"
        ).json()
        self.assertEqual(data["status_actions"], ["alumni"])
        self.assertEqual(
            self._post(self.ceo, "alumni", WRITE_UP).status_code, 200
        )
        self.assertEqual(self._status(), "alumni")

    def test_alumni_twice_is_refused(self, queue_dm):
        self._post(self.ceo, "alumni", WRITE_UP)
        self.assertEqual(
            self._post(self.ceo, "alumni", WRITE_UP).status_code, 400
        )

    def test_alumni_tasks_are_paused(self, queue_dm):
        self.assertFalse(is_paused(self.user))
        self._post(self.ceo, "alumni", WRITE_UP)
        self.assertTrue(is_paused(self.user))


class AlumniMessageTestCase(TestCase):
    def test_multi_line_write_up_is_quoted(self):
        ceo = User.objects.create(username="ceo")
        message = alumni_message(ceo, self.user, "First line\n\nSecond line")
        self.assertIn("> First line\n> Second line", message)
        self.assertIn("ceo wrote", message)
