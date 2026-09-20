"""What happens when the things we depend on misbehave.

ESI returns 500s and 420s, notification bodies change shape, killmails
arrive with fields missing, and the cache goes away. None of that may take
a campaign's numbers with it.
"""

from unittest import mock

import requests
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from campaigns.helpers import campaign_day
from campaigns.models import CampaignKillmail, CampaignParticipantDay
from campaigns.services import esi_gate, sites, snapshots, stats
from campaigns.services.attribution import attribute_feed_killmail
from campaigns.tasks import poll_campaign_payouts
from campaigns.tests.helpers import (
    KAMELA,
    enlist,
    make_campaign,
    make_feed_killmail,
)
from eveonline.models import EveCharacterFwLpPayout
from feed.models import FeedKillmail


class PayoutParsingTests(TestCase):
    """The notification body is text CCP renders; it will change on us."""

    def setUp(self):
        self.campaign = make_campaign()
        self.user, self.character = enlist(self.campaign, "pilot", 9001)

    def _store(self, text, notification_id=1, timestamp=None):
        return sites.store_payout(
            self.character,
            {
                "notification_id": notification_id,
                "type": "FacWarLPPayoutEvent",
                "timestamp": timestamp or timezone.now(),
                "text": text,
            },
        )

    def test_an_empty_body_does_not_explode(self):
        payout = self._store("")
        self.assertIsNotNone(payout)
        self.assertEqual(payout.amount_lp, 0)

    def test_junk_in_the_body_is_survivable(self):
        for index, text in enumerate(
            [
                "not: yaml: at all: ::::",
                "amount: not-a-number\nevent: also-not",
                "\x00\x01\x02",
                "amount: 1e400",
                "A" * 20000,
                "amount:\nevent:\nlocationID:",
            ]
        ):
            payout = self._store(text, notification_id=100 + index)
            self.assertIsNotNone(payout, text[:20])

    def test_a_notification_that_is_not_a_payout_is_ignored(self):
        self.assertIsNone(
            sites.store_payout(
                self.character,
                {
                    "notification_id": 5,
                    "type": "StructureUnderAttack",
                    "timestamp": timezone.now(),
                    "text": "amount: 500",
                },
            )
        )

    def test_a_notification_with_no_id_is_ignored(self):
        self.assertIsNone(
            sites.store_payout(
                self.character,
                {
                    "type": "FacWarLPPayoutEvent",
                    "timestamp": timezone.now(),
                    "text": "amount: 500",
                },
            )
        )

    def test_the_same_notification_twice_is_stored_once(self):
        self._store("amount: 500\nevent: 371", notification_id=7)
        self._store("amount: 500\nevent: 371", notification_id=7)
        self.assertEqual(EveCharacterFwLpPayout.objects.count(), 1)


class MalformedKillmailTests(TestCase):
    """The stream is somebody else's JSON."""

    def setUp(self):
        self.campaign = make_campaign()
        self.user, _ = enlist(self.campaign, "pilot", 9101)

    def _raw(self, killmail_id, raw, zkb=None):
        return FeedKillmail.objects.create(
            killmail_id=killmail_id,
            hash="x",
            killmail_time=timezone.now(),
            solar_system_id=KAMELA,
            attacker_summary=[],
            raw_killmail=raw,
            zkb_meta=zkb or {},
        )

    def test_a_killmail_with_no_victim_or_attackers_is_ignored(self):
        for index, raw in enumerate(
            [
                {},
                {"victim": {}},
                {"attackers": []},
                {"victim": None, "attackers": None},
            ]
        ):
            feed_killmail = self._raw(400 + index, raw)
            self.assertEqual(attribute_feed_killmail(feed_killmail), 0)

    def test_attackers_without_character_ids_are_ignored(self):
        feed_killmail = self._raw(
            410,
            {
                "victim": {"character_id": 9999},
                "attackers": [{"ship_type_id": 1}, {"character_id": None}],
            },
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 0)

    def test_a_missing_isk_value_counts_as_nothing(self):
        feed_killmail = self._raw(
            411,
            {
                "victim": {"character_id": 9999},
                "attackers": [{"character_id": 9101, "final_blow": True}],
            },
            zkb={},
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 1)
        self.assertEqual(CampaignKillmail.objects.get().isk_value, 0)

    def test_a_thousand_attackers_is_just_a_big_blob(self):
        feed_killmail = self._raw(
            412,
            {
                "victim": {"character_id": 9999},
                "attackers": [
                    {"character_id": 9101 if i == 0 else 500000 + i}
                    for i in range(1000)
                ],
            },
            zkb={"totalValue": 10_000_000},
        )
        self.assertEqual(attribute_feed_killmail(feed_killmail), 1)

        mail = CampaignKillmail.objects.get()
        self.assertEqual(mail.attacker_count, 1000)
        self.assertEqual(mail.enlisted_attacker_count, 1)
        # One of ours on the mail means one participant row, not a thousand.
        self.assertEqual(mail.participants.count(), 1)


class EsiFailureTests(TestCase):
    """ESI answers 500, 420 and nonsense, and sometimes just hangs up."""

    def setUp(self):
        cache.clear()
        self.campaign = make_campaign()
        self.user, self.character = enlist(self.campaign, "pilot", 9201)

    def _poll(self):
        return poll_campaign_payouts()

    def test_a_failing_esi_call_does_not_lose_the_batch(self):
        failure = mock.Mock()
        failure.success.return_value = False
        failure.error_text.return_value = "ESI is having a moment"

        with mock.patch(
            "eveonline.client.EsiClient.get_character_notifications",
            return_value=failure,
        ):
            result = self._poll()

        self.assertEqual(result["stored"], 0)
        self.assertLess(esi_gate.error_budget(), 100)

    def test_an_exception_from_esi_does_not_abort_the_batch(self):
        with mock.patch(
            "eveonline.client.EsiClient.get_character_notifications",
            side_effect=ConnectionError("socket hung up"),
        ):
            result = self._poll()

        self.assertEqual(result["polled"], 0)
        self.assertEqual(result["stored"], 0)

    def test_nonsense_from_esi_is_not_stored(self):
        response = mock.Mock()
        response.success.return_value = True
        response.results.return_value = [
            {},
            {"type": "Nope"},
            {"notification_id": None},
            None,
        ]

        with mock.patch(
            "eveonline.client.EsiClient.get_character_notifications",
            return_value=response,
        ):
            result = self._poll()

        self.assertEqual(result["stored"], 0)

    def test_the_snapshot_poll_survives_a_dead_endpoint(self):
        with mock.patch(
            "requests.get", side_effect=requests.RequestException("boom")
        ):
            self.assertEqual(snapshots.fetch_fw_systems(), [])
            self.assertEqual(
                snapshots.record_snapshots(), {"systems": 0, "written": 0}
            )


class CacheOutageTests(TestCase):
    """Redis is an optimisation over ESI's own limits, not a dependency."""

    def test_the_gate_allows_work_when_the_cache_is_down(self):
        with mock.patch(
            "django.core.cache.cache.get", side_effect=ConnectionError("down")
        ), mock.patch(
            "django.core.cache.cache.set", side_effect=ConnectionError("down")
        ):
            self.assertTrue(esi_gate.can_spend("char-notification", 1))
            self.assertEqual(esi_gate.error_budget(), 100)

    def test_spending_survives_a_cache_that_throws(self):
        with mock.patch(
            "django.core.cache.cache.get_or_set",
            side_effect=ConnectionError("down"),
        ):
            self.assertTrue(esi_gate.spend("char-notification", 1))


class ScoringUnderChaosTests(TestCase):
    """The numbers have to hold up when the inputs are ugly."""

    def setUp(self):
        self.campaign = make_campaign()
        self.user, self.character = enlist(self.campaign, "pilot", 9301)
        self.today = campaign_day()

    def test_a_day_of_nothing_but_losses_never_goes_negative(self):
        for index in range(30):
            feed_killmail = make_feed_killmail(
                600 + index,
                victim_character_id=9301,
                attacker_ids=[7777],
                isk_value=2_000_000_000,
            )
            attribute_feed_killmail(feed_killmail)

        stats.materialise_days(self.campaign, [self.today])
        row = CampaignParticipantDay.objects.get(campaign=self.campaign)
        self.assertEqual(row.losses, 30)
        self.assertGreaterEqual(row.points, 0)

    def test_an_absurd_isk_value_cannot_run_away_with_the_board(self):
        feed_killmail = make_feed_killmail(
            650,
            victim_character_id=9999,
            attacker_ids=[9301],
            isk_value=9_000_000_000_000_000,
        )
        attribute_feed_killmail(feed_killmail)
        stats.materialise_days(self.campaign, [self.today])

        row = CampaignParticipantDay.objects.get(campaign=self.campaign)
        # One kill is one kill, however expensive the hull was.
        self.assertLess(row.points, 200)

    def test_a_payout_of_an_impossible_size_is_not_classified(self):
        result = sites.infer_complex_class(
            amount_lp=10**12,
            split_count=1,
            operational_state="frontline",
            contested=0.5,
            suppression=1.0,
        )
        self.assertIsNone(result["base_lp_tier"])
        self.assertEqual(result["confidence"], "unknown")

    def test_a_zero_contest_reading_does_not_divide_by_zero(self):
        result = sites.infer_complex_class(
            amount_lp=5_000,
            split_count=1,
            operational_state="rearguard",
            contested=0.0,
            suppression=1.0,
        )
        self.assertEqual(result["confidence"], "unknown")
