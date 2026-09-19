"""Attribution is the one thing that must never lose a kill."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from campaigns.models import (
    CampaignKillmail,
    CampaignStatus,
    KillmailOutcome,
)
from campaigns.services.attribution import (
    attribute_feed_killmail,
    sweep_recent,
)
from campaigns.tests.helpers import (
    enlist,
    make_campaign,
    make_feed_killmail,
)

AMAMAKE = 30002537


class AttributionTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.user, self.character = enlist(self.campaign, "pilot", 1001)

    def test_kill_by_enlisted_character_is_a_kill(self):
        feed_killmail = make_feed_killmail(
            1, victim_character_id=9999, attacker_ids=[1001]
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 1)

        mail = CampaignKillmail.objects.get(campaign=self.campaign)
        self.assertEqual(mail.outcome, KillmailOutcome.KILL)
        self.assertEqual(mail.enlisted_attacker_count, 1)
        self.assertEqual(mail.participants.count(), 1)

    def test_loss_of_an_enlisted_character_is_a_loss(self):
        feed_killmail = make_feed_killmail(
            2, victim_character_id=1001, attacker_ids=[9999]
        )
        attribute_feed_killmail(feed_killmail)

        mail = CampaignKillmail.objects.get(campaign=self.campaign)
        self.assertEqual(mail.outcome, KillmailOutcome.LOSS)

    def test_enlisted_on_both_sides_is_an_awox(self):
        enlist(self.campaign, "traitor", 1002)
        feed_killmail = make_feed_killmail(
            3, victim_character_id=1001, attacker_ids=[1002]
        )
        attribute_feed_killmail(feed_killmail)

        mail = CampaignKillmail.objects.get(campaign=self.campaign)
        self.assertEqual(mail.outcome, KillmailOutcome.AWOX)

    def test_mail_with_nobody_of_ours_is_ignored(self):
        feed_killmail = make_feed_killmail(
            4, victim_character_id=8888, attacker_ids=[9999]
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 0)
        self.assertEqual(CampaignKillmail.objects.count(), 0)

    def test_mail_outside_the_campaign_systems_is_ignored(self):
        feed_killmail = make_feed_killmail(
            5,
            solar_system_id=AMAMAKE,
            victim_character_id=9999,
            attacker_ids=[1001],
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 0)

    def test_kill_before_the_pilot_enlisted_does_not_count(self):
        """Attribution starts at enlistment. There is no backfill."""
        _, _ = enlist(
            self.campaign,
            "latecomer",
            1003,
            enlisted_at=timezone.now() - timedelta(hours=1),
            included_from=timezone.now() - timedelta(hours=1),
        )
        feed_killmail = make_feed_killmail(
            6,
            victim_character_id=9999,
            attacker_ids=[1003],
            killmail_time=timezone.now() - timedelta(days=3),
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 0)

    def test_kill_after_a_character_is_excluded_does_not_count(self):
        enlist(
            self.campaign,
            "parked",
            1004,
            included_until=timezone.now() - timedelta(hours=2),
        )
        feed_killmail = make_feed_killmail(
            7, victim_character_id=9999, attacker_ids=[1004]
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 0)

    def test_draft_campaigns_do_not_attribute(self):
        self.campaign.status = CampaignStatus.DRAFT
        self.campaign.save()
        feed_killmail = make_feed_killmail(
            8, victim_character_id=9999, attacker_ids=[1001]
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 0)

    def test_scheduled_campaigns_attribute_so_nothing_is_missed(self):
        """A campaign is created before it starts; the hook is already live."""
        self.campaign.status = CampaignStatus.SCHEDULED
        self.campaign.save()
        feed_killmail = make_feed_killmail(
            9, victim_character_id=9999, attacker_ids=[1001]
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 1)

    def test_attribution_is_idempotent_and_records_every_source(self):
        feed_killmail = make_feed_killmail(
            10, victim_character_id=9999, attacker_ids=[1001]
        )
        attribute_feed_killmail(feed_killmail, source="stream")
        attribute_feed_killmail(feed_killmail, source="sweep")

        self.assertEqual(CampaignKillmail.objects.count(), 1)
        mail = CampaignKillmail.objects.get()
        self.assertEqual(mail.first_seen_via, "stream")
        self.assertCountEqual(mail.sources, ["stream", "sweep"])

    def test_sweep_recovers_a_mail_the_stream_never_attributed(self):
        make_feed_killmail(11, victim_character_id=9999, attacker_ids=[1001])
        self.assertEqual(CampaignKillmail.objects.count(), 0)

        result = sweep_recent(hours=48)
        self.assertEqual(result["attributed"], 1)
        self.assertEqual(CampaignKillmail.objects.count(), 1)
