"""Two campaigns can cover the same system at the same time.

The plan allows it, so a kill in Kamela has to count for both without either
stealing from the other or double-counting inside one.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from campaigns.helpers import campaign_day
from campaigns.models import (
    CampaignEvent,
    CampaignKillmail,
    CampaignParticipantDay,
    KillmailOutcome,
    SystemGoal,
)
from campaigns.services import snapshots, stats
from campaigns.services.attribution import attribute_feed_killmail
from campaigns.tests.helpers import (
    KAMELA,
    enlist,
    make_campaign,
    make_feed_killmail,
)
from feed.models import FeedEvent


class OverlappingCampaignTests(TestCase):
    def setUp(self):
        # Both campaigns cover Kamela; make_campaign adds it to each.
        self.first = make_campaign()
        self.second = make_campaign(
            slug="second-push", short_code="SEC", name="Second Push"
        )
        self.second.systems.update(goal=SystemGoal.DEFEND)

        # One pilot, one character, flying for both.
        self.both, self.character = enlist(self.first, "double", 9501)
        enlistment = self.second.enlistments.create(
            user=self.both, status="active"
        )
        enlistment.periods.create(enlisted_at=self.second.start_at)
        enlistment.characters.create(
            character=self.character, included_from=self.second.start_at
        )

    def test_one_kill_counts_once_in_each_campaign(self):
        feed_killmail = make_feed_killmail(
            980, victim_character_id=9999, attacker_ids=[9501]
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 2)

        for campaign in (self.first, self.second):
            mails = CampaignKillmail.objects.filter(campaign=campaign)
            self.assertEqual(mails.count(), 1, campaign.slug)
            self.assertEqual(mails.get().outcome, KillmailOutcome.KILL)

    def test_re_attributing_does_not_duplicate_in_either(self):
        feed_killmail = make_feed_killmail(
            981, victim_character_id=9999, attacker_ids=[9501]
        )
        for _ in range(3):
            attribute_feed_killmail(feed_killmail)

        self.assertEqual(CampaignKillmail.objects.count(), 2)

    def test_points_are_earned_separately_in_each_campaign(self):
        feed_killmail = make_feed_killmail(
            982, victim_character_id=9999, attacker_ids=[9501]
        )
        attribute_feed_killmail(feed_killmail)

        today = campaign_day()
        for campaign in (self.first, self.second):
            stats.materialise_days(campaign, [today])

        rows = CampaignParticipantDay.objects.filter(user=self.both, day=today)
        self.assertEqual(rows.count(), 2)
        for row in rows:
            self.assertEqual(row.kills, 1)
            self.assertGreater(row.points, 0)

    def test_leaving_one_campaign_does_not_touch_the_other(self):
        enlistment = self.first.enlistments.get(user=self.both)
        enlistment.status = "left"
        enlistment.save()
        enlistment.periods.update(left_at=timezone.now() - timedelta(hours=1))

        feed_killmail = make_feed_killmail(
            983, victim_character_id=9999, attacker_ids=[9501]
        )
        attribute_feed_killmail(feed_killmail)

        self.assertFalse(
            CampaignKillmail.objects.filter(campaign=self.first).exists()
        )
        self.assertTrue(
            CampaignKillmail.objects.filter(campaign=self.second).exists()
        )

    def test_a_feed_event_is_mirrored_into_both_timelines(self):
        FeedEvent.objects.create(
            kind="fleet_active",
            occurred_at=timezone.now(),
            title="Amarr gang in Kamela",
            accent="amarr",
            rollup_code="fleet_active",
            payload={"system_id": KAMELA},
            is_active=True,
        )

        for campaign in (self.first, self.second):
            self.assertEqual(snapshots.mirror_feed_events(campaign), 1)
            self.assertEqual(
                CampaignEvent.objects.filter(
                    campaign=campaign, source="feed"
                ).count(),
                1,
                campaign.slug,
            )

    def test_mirroring_twice_does_not_duplicate_the_timeline(self):
        FeedEvent.objects.create(
            kind="killmail_batch",
            occurred_at=timezone.now(),
            title="Kill burst in Kamela",
            accent="combat",
            rollup_code="killmail_batch",
            payload={"system_id": KAMELA},
        )

        for _ in range(3):
            snapshots.mirror_feed_events(self.first)

        self.assertEqual(
            CampaignEvent.objects.filter(
                campaign=self.first, source="feed"
            ).count(),
            1,
        )
