"""Killmails carry ids, not names. The killfeed needs names."""

from unittest import mock

from django.test import TestCase

from campaigns.models import CampaignKillmail
from campaigns.services import names
from campaigns.tests.helpers import (
    enlist,
    make_campaign,
    make_feed_killmail,
)
from campaigns.services.attribution import attribute_feed_killmail


class VictimNameTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.user, self.character = enlist(self.campaign, "pilot", 5001)

    def _make_kill(self, killmail_id, victim_id):
        feed_killmail = make_feed_killmail(
            killmail_id, victim_character_id=victim_id, attacker_ids=[5001]
        )
        attribute_feed_killmail(feed_killmail)

    def test_a_character_we_already_know_is_named_for_free(self):
        """Our own losses need no ESI call at all."""
        self._make_kill(1, 5001)

        with mock.patch(
            "eveonline.client.EsiClient.resolve_universe_names"
        ) as resolver:
            result = names.backfill_victim_names()
            resolver.assert_not_called()

        self.assertEqual(result["named"], 1)
        self.assertEqual(result["from_esi"], 0)
        mail = CampaignKillmail.objects.get(killmail_id=1)
        self.assertEqual(mail.victim_character_name, "Pilot")

    def test_a_stranger_is_resolved_from_esi(self):
        self._make_kill(2, 9001)

        response = mock.Mock()
        response.success.return_value = True
        response.results.return_value = [
            {"id": 9001, "name": "Some Amarr", "category": "character"}
        ]

        with mock.patch(
            "eveonline.client.EsiClient.resolve_universe_names",
            return_value=response,
        ):
            result = names.backfill_victim_names()

        self.assertEqual(result["from_esi"], 1)
        mail = CampaignKillmail.objects.get(killmail_id=2)
        self.assertEqual(mail.victim_character_name, "Some Amarr")

    def test_a_failed_lookup_leaves_the_row_alone_for_next_time(self):
        self._make_kill(3, 9002)

        response = mock.Mock()
        response.success.return_value = False
        response.error_text.return_value = "boom"

        with mock.patch(
            "eveonline.client.EsiClient.resolve_universe_names",
            return_value=response,
        ):
            result = names.backfill_victim_names()

        self.assertEqual(result["named"], 0)
        mail = CampaignKillmail.objects.get(killmail_id=3)
        self.assertEqual(mail.victim_character_name, "")

    def test_nothing_to_do_makes_no_calls(self):
        with mock.patch(
            "eveonline.client.EsiClient.resolve_universe_names"
        ) as resolver:
            result = names.backfill_victim_names()
            resolver.assert_not_called()
        self.assertEqual(result["pending"], 0)

    def test_non_character_results_are_ignored(self):
        self._make_kill(4, 9003)

        response = mock.Mock()
        response.success.return_value = True
        response.results.return_value = [
            {"id": 9003, "name": "Some Corp", "category": "corporation"}
        ]

        with mock.patch(
            "eveonline.client.EsiClient.resolve_universe_names",
            return_value=response,
        ):
            names.backfill_victim_names()

        mail = CampaignKillmail.objects.get(killmail_id=4)
        self.assertEqual(mail.victim_character_name, "")
