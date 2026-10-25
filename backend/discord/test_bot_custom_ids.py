"""
The backend posts Discord buttons that the bot (a separate deployable in
bot/) handles. Both sides must agree on the custom_ids, and posted messages
keep theirs forever. bot/app/custom_ids.py is the bot's definition; this test
loads it by path and checks every id the backend builds against it.
"""

import importlib.util
import os
import re
from pathlib import Path
from unittest import skipUnless

from django.test import SimpleTestCase

from buyback.helpers.purchase_discord_buttons import (
    CANCEL_CUSTOM_ID_PREFIX,
    COMPLETE_CUSTOM_ID_PREFIX,
    cancel_custom_id,
    complete_custom_id,
)
from fleets.helpers.npsi_discord import (
    POST_CUSTOM_ID_PREFIX,
    PREPING_CUSTOM_ID_PREFIX,
    TRACK_CUSTOM_ID_PREFIX,
    post_custom_id,
    preping_custom_id,
    track_custom_id,
)
from fleets.helpers.private_fleet_discord import (
    SIT_OUT_CUSTOM_ID_PREFIX,
    STOP_INVITES_CUSTOM_ID_PREFIX,
    sit_out_custom_id,
    stop_invites_custom_id,
)
from industry.helpers.lp_buyback_discord_buttons import (
    ISK_SENT_CUSTOM_ID_PREFIX,
    LP_SENT_CUSTOM_ID_PREFIX,
    isk_sent_custom_id,
    lp_sent_custom_id,
)
from notifications.discord_buttons import (
    NOTIF_ACK_CUSTOM_ID_PREFIX,
    ack_custom_id,
)
from tribes.helpers.invitation_discord import (
    DECLINE_CUSTOM_ID_PREFIX,
    decline_custom_id,
)

BOT_CUSTOM_IDS = (
    Path(__file__).resolve().parents[2] / "bot" / "app" / "custom_ids.py"
)


def _load_bot_custom_ids():
    spec = importlib.util.spec_from_file_location(
        "bot_custom_ids", BOT_CUSTOM_IDS
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BotCustomIdsPresentTestCase(SimpleTestCase):
    def test_bot_definition_is_checked_out_in_ci(self):
        # The backend image ships without bot/, so the parity test skips
        # there; in CI (a full checkout) it must run.
        if os.environ.get("CI"):
            self.assertTrue(BOT_CUSTOM_IDS.exists(), BOT_CUSTOM_IDS)


@skipUnless(BOT_CUSTOM_IDS.exists(), "bot/ is not checked out")
class BotCustomIdParityTestCase(SimpleTestCase):
    def setUp(self):
        self.bot = _load_bot_custom_ids()

    def test_prefixes_match(self):
        pairs = [
            (COMPLETE_CUSTOM_ID_PREFIX, self.bot.BUYBACK_COMPLETE_PREFIX),
            (CANCEL_CUSTOM_ID_PREFIX, self.bot.BUYBACK_CANCEL_PREFIX),
            (LP_SENT_CUSTOM_ID_PREFIX, self.bot.LP_BUYBACK_LP_SENT_PREFIX),
            (ISK_SENT_CUSTOM_ID_PREFIX, self.bot.LP_BUYBACK_ISK_SENT_PREFIX),
            (NOTIF_ACK_CUSTOM_ID_PREFIX, self.bot.NOTIF_ACK_PREFIX),
            (POST_CUSTOM_ID_PREFIX, self.bot.NPSI_POST_PREFIX),
            (PREPING_CUSTOM_ID_PREFIX, self.bot.NPSI_PREPING_PREFIX),
            (TRACK_CUSTOM_ID_PREFIX, self.bot.NPSI_TRACK_PREFIX),
            (DECLINE_CUSTOM_ID_PREFIX, self.bot.TRIBE_INVITE_DECLINE_PREFIX),
            (SIT_OUT_CUSTOM_ID_PREFIX, self.bot.FLEET_INVITE_OUT_PREFIX),
            (
                STOP_INVITES_CUSTOM_ID_PREFIX,
                self.bot.FLEET_INVITE_STOP_PREFIX,
            ),
        ]
        for backend, bot in pairs:
            self.assertEqual(backend, bot)

    def test_every_backend_id_matches_a_bot_template(self):
        pairs = [
            (complete_custom_id, self.bot.BUYBACK_COMPLETE_TEMPLATE),
            (cancel_custom_id, self.bot.BUYBACK_CANCEL_TEMPLATE),
            (lp_sent_custom_id, self.bot.LP_BUYBACK_LP_SENT_TEMPLATE),
            (isk_sent_custom_id, self.bot.LP_BUYBACK_ISK_SENT_TEMPLATE),
            (ack_custom_id, self.bot.NOTIF_ACK_TEMPLATE),
            (post_custom_id, self.bot.NPSI_POST_TEMPLATE),
            (preping_custom_id, self.bot.NPSI_PREPING_TEMPLATE),
            (track_custom_id, self.bot.NPSI_TRACK_TEMPLATE),
            (decline_custom_id, self.bot.TRIBE_INVITE_DECLINE_TEMPLATE),
            (sit_out_custom_id, self.bot.FLEET_INVITE_OUT_TEMPLATE),
            (stop_invites_custom_id, self.bot.FLEET_INVITE_STOP_TEMPLATE),
        ]
        for build, template in pairs:
            built = build(1234567890123)
            match = re.fullmatch(template, built)
            self.assertIsNotNone(match, f"{built!r} vs {template!r}")
            self.assertEqual("1234567890123", match.groups()[0])
