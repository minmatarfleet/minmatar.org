from datetime import timedelta

import factory
from django.contrib.auth.models import User
from django.db.models import signals
from django.test import TestCase
from django.utils import timezone

from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCorporation,
    EvePlayer,
)
from groups.models import UserCommunityStatusHistory
from surveys.helpers.tenure import member_join_date, tenure_days

FL33T_ALLIANCE_ID = 99011978


class TenureTests(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def setUp(self):
        self.user = User.objects.create(username="pilot")
        self.alliance = EveAlliance.objects.create(
            alliance_id=FL33T_ALLIANCE_ID
        )
        self.corp = EveCorporation.objects.create(
            corporation_id=98000001,
            name="Rattini Tribe",
            ticker="A-RAT",
            alliance=self.alliance,
        )
        self.character = EveCharacter.objects.create(
            character_id=90000001,
            character_name="Testpilot",
            corporation_id=self.corp.corporation_id,
            alliance_id=FL33T_ALLIANCE_ID,
            user=self.user,
        )
        EvePlayer.objects.create(
            user=self.user,
            primary_character=self.character,
            nickname=self.user.username,
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_corp_history_beats_recent_community_status(self):
        """Tenure must reflect the real corp-join date, not the recently-launched
        community-status audit log (regression for the 171d bug)."""
        joined_at = timezone.now() - timedelta(days=1376)
        EveCharacterCorporationHistory.objects.create(
            character=self.character,
            record_id=1,
            corporation_id=self.corp.corporation_id,
            start_date=joined_at,
        )
        # A far more recent community-status row must NOT win.
        UserCommunityStatusHistory.objects.create(
            user=self.user, to_status="active"
        )

        self.assertEqual(member_join_date(self.user), joined_at)
        self.assertEqual(tenure_days(self.user), 1376)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_earliest_alliance_stint_wins_across_multiple_corps(self):
        """A move between two alliance corps counts from the first alliance corp."""
        second_corp = EveCorporation.objects.create(
            corporation_id=98000002,
            name="Rattini Academy",
            ticker="L3ARN",
            alliance=self.alliance,
        )
        first = timezone.now() - timedelta(days=1000)
        second = timezone.now() - timedelta(days=200)
        EveCharacterCorporationHistory.objects.create(
            character=self.character,
            record_id=1,
            corporation_id=second_corp.corporation_id,
            start_date=first,
        )
        EveCharacterCorporationHistory.objects.create(
            character=self.character,
            record_id=2,
            corporation_id=self.corp.corporation_id,
            start_date=second,
        )

        self.assertEqual(member_join_date(self.user), first)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_falls_back_when_no_corp_history(self):
        """With no corp history, tenure falls back to the community-status log."""
        UserCommunityStatusHistory.objects.create(
            user=self.user, to_status="active"
        )
        joined = member_join_date(self.user)
        self.assertIsNotNone(joined)
        # No corp history rows exist, so the fallback signal is used.
        self.assertEqual(
            EveCharacterCorporationHistory.objects.filter(
                character=self.character
            ).count(),
            0,
        )
