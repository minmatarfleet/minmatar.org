"""Corp officers are matched by one ownership rule on the corp page and in
alliance health: a character's user, or its token's user only when the
character has no user."""

from contextlib import ExitStack

import factory
from django.contrib.auth.models import User
from django.db.models import signals
from django.test import TestCase
from esi.models import Token

from alliance.helpers.access import (
    can_view_health,
    ceo_corp_ids,
    officer_corp_ids,
)
from eveonline.helpers.corporations.permissions import (
    can_manage_corporation,
    user_is_ceo,
    user_is_director,
)
from eveonline.models import EveAlliance, EveCharacter, EveCorporation

ALLIANCE_ID = 99011978


class OfficerAccessTest(TestCase):
    def setUp(self):
        stack = ExitStack()
        stack.enter_context(
            factory.django.mute_signals(signals.pre_save, signals.post_save)
        )
        self.addCleanup(stack.close)
        alliance = EveAlliance.objects.create(
            alliance_id=ALLIANCE_ID, name="Minmatar Fleet Alliance"
        )
        self.linked = User.objects.create(username="linked")
        self.token_only = User.objects.create(username="token_only")
        self.stale = User.objects.create(username="stale")
        self.corp = EveCorporation.objects.create(
            corporation_id=98000001, name="Corp", ticker="CORP"
        )
        self.corp.alliance = alliance
        self.corp.save()
        self.hold = EveCorporation.objects.create(
            corporation_id=98000002, name="Hold", ticker="MH0LD"
        )
        self.hold.alliance = alliance
        self.hold.save()

    def _char(self, cid, user=None, token_user=None):
        token = (
            Token.objects.create(character_id=cid, user=token_user)
            if token_user
            else None
        )
        return EveCharacter.objects.create(
            character_id=cid, character_name=f"c{cid}", user=user, token=token
        )

    def test_token_only_ceo_is_an_officer_everywhere(self):
        self.corp.ceo = self._char(1, token_user=self.token_only)
        self.corp.save()
        self.assertTrue(user_is_ceo(self.token_only, self.corp))
        self.assertTrue(can_manage_corporation(self.token_only, self.corp))
        # Alliance health used to ignore the token link.
        self.assertEqual(ceo_corp_ids(self.token_only), {98000001})
        self.assertEqual(officer_corp_ids(self.token_only), {98000001})
        self.assertTrue(can_view_health(self.token_only))

    def test_token_only_director_can_manage_and_view_health(self):
        self.corp.directors.add(self._char(2, token_user=self.token_only))
        self.assertTrue(user_is_director(self.token_only, self.corp))
        # can_manage_corporation used to check director.user only.
        self.assertTrue(can_manage_corporation(self.token_only, self.corp))
        self.assertEqual(officer_corp_ids(self.token_only), {98000001})
        self.assertEqual(ceo_corp_ids(self.token_only), set())

    def test_user_linked_officers_still_pass(self):
        self.corp.ceo = self._char(3, user=self.linked)
        self.corp.save()
        self.corp.directors.add(self._char(4, user=self.linked))
        self.assertTrue(user_is_ceo(self.linked, self.corp))
        self.assertTrue(user_is_director(self.linked, self.corp))
        self.assertTrue(can_manage_corporation(self.linked, self.corp))
        self.assertEqual(officer_corp_ids(self.linked), {98000001})

    def test_stale_token_user_is_not_the_officer(self):
        # Character moved to `linked`; its old token still names `stale`.
        self.corp.ceo = self._char(5, user=self.linked, token_user=self.stale)
        self.corp.save()
        self.corp.directors.add(
            self._char(6, user=self.linked, token_user=self.stale)
        )
        self.assertFalse(user_is_ceo(self.stale, self.corp))
        self.assertFalse(user_is_director(self.stale, self.corp))
        self.assertFalse(can_manage_corporation(self.stale, self.corp))
        self.assertEqual(officer_corp_ids(self.stale), set())
        self.assertTrue(user_is_ceo(self.linked, self.corp))

    def test_mh0ld_stays_out_of_health(self):
        self.hold.ceo = self._char(7, user=self.linked)
        self.hold.save()
        self.assertTrue(can_manage_corporation(self.linked, self.hold))
        self.assertEqual(officer_corp_ids(self.linked), set())
