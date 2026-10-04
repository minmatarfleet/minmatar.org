"""Advantage read off CCP's frontlines page instead of reported by pilots."""

from unittest.mock import patch

from django.test import TestCase

from campaigns.models import CampaignAdvantageReading, CampaignSystem
from campaigns.services import advantage, frontlines, snapshots
from campaigns.tasks import poll_frontlines_advantage
from campaigns.tests.helpers import KAMELA, enlist, make_campaign


def _entry(system_id, ours, theirs, contested=0.5):
    return {
        "solarsystemID": system_id,
        "ownerFaction": 500003,
        "occupierFaction": 500003,
        "contestedStatus": "Contested",
        "contestedAmount": contested,
        "advantage": [
            {"factionID": 500002, "totalAmount": ours},
            {"factionID": 500003, "totalAmount": theirs},
            {"factionID": 500011, "totalAmount": 0},
        ],
    }


class FrontlinesAdvantageTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.system = self.campaign.systems.first()

    def test_a_status_entry_becomes_an_exact_reading(self):
        result = frontlines.record_advantage([_entry(KAMELA, 96, 53)])

        self.assertEqual(result, {"systems": 1, "written": 1})
        reading = CampaignAdvantageReading.objects.get(
            campaign_system=self.system
        )
        self.assertEqual(reading.source, "frontlines")
        self.assertEqual(reading.status, "accepted")
        card = advantage.card_for(self.system)
        self.assertEqual(card["our_pct"], 96.0)
        self.assertEqual(card["enemy_pct"], 53.0)
        self.assertEqual(card["source"], "frontlines")
        self.assertEqual(card["basis"], "reading")

    def test_force_writes_an_unchanged_reading(self):
        frontlines.record_advantage([_entry(KAMELA, 96, 53)])
        result = frontlines.record_advantage(
            [_entry(KAMELA, 96, 53)], force=True
        )
        self.assertEqual(result["written"], 1)
        self.assertEqual(
            CampaignAdvantageReading.objects.filter(
                campaign_system=self.system
            ).count(),
            2,
        )

    def test_an_unchanged_number_is_not_written_twice(self):
        frontlines.record_advantage([_entry(KAMELA, 96, 53)])
        result = frontlines.record_advantage([_entry(KAMELA, 96, 53)])
        self.assertEqual(result["written"], 0)
        self.assertEqual(
            CampaignAdvantageReading.objects.filter(
                campaign_system=self.system
            ).count(),
            1,
        )

    def test_a_moved_number_is_written(self):
        frontlines.record_advantage([_entry(KAMELA, 96, 53)])
        result = frontlines.record_advantage([_entry(KAMELA, 98, 53)])
        self.assertEqual(result["written"], 1)
        self.assertEqual(advantage.card_for(self.system)["our_pct"], 98.0)

    def test_the_frontlines_number_is_not_averaged_with_pilot_guesses(self):
        user, _ = enlist(self.campaign, "guesser", 7001)
        advantage.record_reading(self.system, user, 40.0, 40.0)
        frontlines.record_advantage([_entry(KAMELA, 96, 53)])

        # Django caches the reverse one-to-one on the instance we reported
        # with; the card has to be read off a fresh row.
        card = advantage.card_for(
            CampaignSystem.objects.get(id=self.system.id)
        )
        self.assertEqual(card["our_pct"], 96.0)
        self.assertEqual(card["enemy_pct"], 53.0)

    def test_a_system_outside_the_warzone_is_skipped(self):
        result = frontlines.record_advantage([_entry(30000001, 10, 10)])
        self.assertEqual(result, {"systems": 0, "written": 0})

    def test_an_unreachable_page_changes_nothing(self):
        result = frontlines.record_advantage([])
        self.assertEqual(result, {"systems": 0, "written": 0})

    def test_a_system_with_no_snapshot_is_waiting_for_contested(self):
        self.assertTrue(
            snapshots.fw_systems_without_snapshots()
            .filter(id=self.system.id)
            .exists()
        )

    @patch(
        "campaigns.tasks.snapshots.record_snapshots",
        return_value={"written": 1, "systems": 1},
    )
    @patch(
        "campaigns.tasks.frontlines.record_advantage",
        return_value={"written": 0, "systems": 0},
    )
    def test_advantage_poll_pulls_contested_when_none_exists(
        self, advantage_poll, pull
    ):
        result = poll_frontlines_advantage()
        pull.assert_called_once_with()
        self.assertEqual(result["snapshots"], 1)
